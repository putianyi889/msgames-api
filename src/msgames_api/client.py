"""Connection-pooling clients for the site's anonymous, public GET requests."""

import asyncio
import math
import threading
import time
from datetime import date
from types import TracebackType
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit

import httpx

from .exceptions import (
    AccessDeniedError,
    DownloadError,
    HTTPError,
    NotFoundError,
    RateLimitError,
    RequestError,
    ResponseTooLargeError,
)
from .models import (
    DensityBoard,
    Option,
    Profile,
    RankingMetric,
    RankingPage,
    RankingSort,
    Record,
    RecordMetric,
    Replay,
    WorldRecord,
)
from .parsers import (
    BASE_URL,
    REPLAY_EXTENSIONS,
    parse_options,
    parse_profile,
    parse_ranking,
    parse_records,
    parse_world_records,
)

_USER_AGENT = "msgames-api/0.1.1 (+https://github.com/putianyi889/msgames-api)"
_REDIRECTS = {301, 302, 303, 307, 308}


def _id(value: int, name: str = "player_id", *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _start(value: int) -> int:
    _id(value, "start", minimum=0)
    if value % 100:
        raise ValueError("start must be a multiple of 100")
    return value


def _url(url: str, *, replay: bool = False) -> str:
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.hostname not in {"minesweepergame.com", "www.minesweepergame.com"}
        or parts.port not in {None, 443}
        or parts.username
        or parts.password
        or parts.fragment
    ):
        raise ValueError("Only public HTTPS URLs on minesweepergame.com are supported")
    if replay:
        path = unquote(unquote(parts.path))
        if (
            not path.startswith(("/member/file/", "/record/"))
            or "\\" in path
            or any(p in {"..", "."} for p in path.split("/"))
            or not any(path.lower().endswith(ext) for ext in REPLAY_EXTENSIONS)
        ):
            raise ValueError("Expected a public replay link under /member/file/ or /record/")
    return url


def _status(response: httpx.Response) -> None:
    code, url = response.status_code, str(response.url)
    if code == 429:
        raise RateLimitError(url, response.headers.get("retry-after"))
    if code in {401, 403}:
        raise AccessDeniedError(f"HTTP {code}: {url}")
    if code == 404:
        raise NotFoundError(code, url)
    if code >= 300 and code not in _REDIRECTS:
        raise HTTPError(code, url)


def _limit(response: httpx.Response, limit: int) -> None:
    length = response.headers.get("content-length", "")
    if length.isdecimal() and int(length) > limit:
        raise ResponseTooLargeError(f"Response exceeds {limit} bytes")


def _binary(data: bytes, content_type: str) -> bytes:
    prefix = data[:512].lstrip(b"\xef\xbb\xbf \t\r\n").lower()
    if not data or "html" in content_type.lower() or prefix.startswith((b"<!doctype", b"<html")):
        raise DownloadError("Replay download returned an empty response or an HTML page")
    return data


class _Configuration:
    def __init__(self, min_interval: float, max_page_bytes: int, max_replay_bytes: int) -> None:
        if not math.isfinite(min_interval) or min_interval < 0:
            raise ValueError("min_interval must be finite and non-negative")
        self.min_interval = min_interval
        self.max_page_bytes = _id(max_page_bytes, "max_page_bytes")
        self.max_replay_bytes = _id(max_replay_bytes, "max_replay_bytes")
        self._next_request = 0.0
        self._closed = False

    def _check_open(self) -> None:
        if self._closed:
            raise RuntimeError("The msgames-api client is closed")


class Client(_Configuration):
    """Synchronous client. Use a context manager or call close()."""

    def __init__(
        self,
        *,
        http_client: httpx.Client | None = None,
        timeout: float = 30,
        min_interval: float = 1.0,
        max_page_bytes: int = 8 * 1024 * 1024,
        max_replay_bytes: int = 64 * 1024 * 1024,
    ) -> None:
        super().__init__(min_interval, max_page_bytes, max_replay_bytes)
        self._http = http_client or httpx.Client(
            timeout=timeout, headers={"User-Agent": _USER_AGENT}
        )
        self._owns_http = http_client is None
        self._lock = threading.RLock()

    def __enter__(self) -> "Client":
        self._check_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._closed = True
                if self._owns_http:
                    self._http.close()

    def _fetch(
        self, url: str, params: dict[str, Any] | None = None, *, replay: bool = False
    ) -> tuple[bytes, str, str]:
        self._check_open()
        url = _url(url, replay=replay)
        limit = self.max_replay_bytes if replay else self.max_page_bytes
        try:
            for _ in range(6):
                time.sleep(max(0, self._next_request - time.monotonic()))
                self._next_request = time.monotonic() + self.min_interval
                with self._http.stream(
                    "GET",
                    url,
                    params=params,
                    follow_redirects=False,
                    headers={"User-Agent": _USER_AGENT},
                ) as response:
                    _status(response)
                    if response.status_code in _REDIRECTS:
                        location = response.headers.get("location")
                        if not location:
                            raise HTTPError(response.status_code, str(response.url))
                        url = _url(urljoin(str(response.url), location), replay=replay)
                        params = None
                        continue
                    _limit(response, limit)
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > limit:
                            raise ResponseTooLargeError(f"Response exceeds {limit} bytes")
                    return bytes(data), str(response.url), response.headers.get("content-type", "")
        except httpx.HTTPError as exc:
            raise RequestError(str(exc)) from exc
        raise RequestError("Too many redirects")

    def _get(self, path: str, params: dict[str, Any] | None = None) -> tuple[str, str]:
        with self._lock:
            data, url, _ = self._fetch(urljoin(BASE_URL, path), params)
        return data.decode("utf-8", errors="replace"), url

    def get_profile(self, player_id: int) -> Profile:
        html, url = self._get("profile.php", {"pid": _id(player_id)})
        return parse_profile(html, player_id, url)

    def get_records(
        self,
        player_id: int,
        metric: RecordMetric = RecordMetric.TIME,
        *,
        deduplicate: bool = True,
    ) -> tuple[Record, ...]:
        metric = RecordMetric(metric)
        html, url = self._get("profile.php", {"pid": _id(player_id), "menu": int(metric)})
        return parse_records(html, player_id, metric, url, deduplicate=deduplicate)

    def get_ranking(
        self,
        metric: RankingMetric = RankingMetric.TIME,
        *,
        source: str = "world",
        start: int = 0,
        sort: RankingSort = RankingSort.TOTAL,
    ) -> RankingPage:
        if source not in {"world", "arbiter"}:
            raise ValueError("source must be 'world' or 'arbiter'")
        metric, sort = RankingMetric(metric), RankingSort(sort)
        html, url = self._get(
            f"common/ajax/ajax-ranking-{source}.php",
            {"rid": int(metric), "start": _start(start), "sort": int(sort)},
        )
        return parse_ranking(html, source, url, int(metric), start)

    def get_density_ranking(
        self,
        board: DensityBoard = DensityBoard.WORLD,
        *,
        mines: int | None = None,
        start: int = 0,
        sort: int = 0,
    ) -> RankingPage:
        board = DensityBoard(board)
        if sort not in range(6):
            raise ValueError("density sort must be between 0 and 5")
        params = {"rid": int(board), "start": _start(start), "sort": sort}
        if mines is not None:
            params["mines"] = _id(mines, "mines")
        html, url = self._get("common/ajax/ajax-ranking-density.php", params)
        return parse_ranking(html, "density", url, int(board), start)

    def get_density_options(self, board: DensityBoard) -> tuple[Option, ...]:
        html, _ = self._get(
            "common/ajax/ajax-ranking-density-menu-mines.php", {"rid": int(DensityBoard(board))}
        )
        return parse_options(html)

    def get_countries(self) -> tuple[Option, ...]:
        html, _ = self._get("country-rankings.php")
        return parse_options(html, "select[name=choose_country] option")

    def get_country_regions(self, country_id: int) -> tuple[Option, ...]:
        html, _ = self._get(
            "common/ajax/ajax-ranking-country-menu-states.php",
            {"cid": _id(country_id, "country_id")},
        )
        return parse_options(html)

    def get_country_ranking(
        self,
        country_id: int,
        metric: RankingMetric = RankingMetric.TIME,
        *,
        region_id: int = 0,
        start: int = 0,
        sort: RankingSort = RankingSort.TOTAL,
    ) -> RankingPage:
        country_id, region_id = (
            _id(country_id, "country_id"),
            _id(region_id, "region_id", minimum=0),
        )
        metric, sort, start = RankingMetric(metric), RankingSort(sort), _start(start)
        # The frontend uses an anonymous PHP session for the country/region.
        # Hold the lock across all three requests to keep that context intact.
        with self._lock:
            self._fetch(
                BASE_URL + "common/ajax/ajax-ranking-country-menu-states.php", {"cid": country_id}
            )
            self._fetch(
                BASE_URL + "common/ajax/ajax-ranking-country-menu-ranking.php", {"sid": region_id}
            )
            data, url, _ = self._fetch(
                BASE_URL + "common/ajax/ajax-ranking-country.php",
                {"rid": int(metric), "start": start, "sort": int(sort)},
            )
        return parse_ranking(
            data.decode("utf-8", errors="replace"), "country", url, int(metric), start
        )

    def get_historical_ranking(self, day: date | str, *, start: int = 0) -> RankingPage:
        day = date.fromisoformat(day) if isinstance(day, str) else day
        html, url = self._get(
            "common/ajax/ajax-ranking-historical.php",
            {"did": day.isoformat(), "start": _start(start)},
        )
        return parse_ranking(html, "historical", url, start=start)

    def get_world_records(self) -> tuple[WorldRecord, ...]:
        html, url = self._get("world-records.php")
        return parse_world_records(html, url)

    def download_replay(self, replay: Replay | str) -> bytes:
        url = replay.url if isinstance(replay, Replay) else replay
        with self._lock:
            data, _, content_type = self._fetch(url, replay=True)
        return _binary(data, content_type)


class AsyncClient(_Configuration):
    """Async counterpart. A client belongs to one asyncio event loop."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 30,
        min_interval: float = 1.0,
        max_page_bytes: int = 8 * 1024 * 1024,
        max_replay_bytes: int = 64 * 1024 * 1024,
    ) -> None:
        super().__init__(min_interval, max_page_bytes, max_replay_bytes)
        self._http = http_client or httpx.AsyncClient(
            timeout=timeout, headers={"User-Agent": _USER_AGENT}
        )
        self._owns_http = http_client is None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "AsyncClient":
        self._check_open()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        async with self._lock:
            if not self._closed:
                self._closed = True
                if self._owns_http:
                    await self._http.aclose()

    async def _fetch(
        self, url: str, params: dict[str, Any] | None = None, *, replay: bool = False
    ) -> tuple[bytes, str, str]:
        self._check_open()
        url = _url(url, replay=replay)
        limit = self.max_replay_bytes if replay else self.max_page_bytes
        try:
            for _ in range(6):
                await asyncio.sleep(max(0, self._next_request - time.monotonic()))
                self._next_request = time.monotonic() + self.min_interval
                async with self._http.stream(
                    "GET",
                    url,
                    params=params,
                    follow_redirects=False,
                    headers={"User-Agent": _USER_AGENT},
                ) as response:
                    _status(response)
                    if response.status_code in _REDIRECTS:
                        location = response.headers.get("location")
                        if not location:
                            raise HTTPError(response.status_code, str(response.url))
                        url = _url(urljoin(str(response.url), location), replay=replay)
                        params = None
                        continue
                    _limit(response, limit)
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > limit:
                            raise ResponseTooLargeError(f"Response exceeds {limit} bytes")
                    return bytes(data), str(response.url), response.headers.get("content-type", "")
        except httpx.HTTPError as exc:
            raise RequestError(str(exc)) from exc
        raise RequestError("Too many redirects")

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> tuple[str, str]:
        async with self._lock:
            data, url, _ = await self._fetch(urljoin(BASE_URL, path), params)
        return data.decode("utf-8", errors="replace"), url

    async def get_profile(self, player_id: int) -> Profile:
        html, url = await self._get("profile.php", {"pid": _id(player_id)})
        return parse_profile(html, player_id, url)

    async def get_records(
        self,
        player_id: int,
        metric: RecordMetric = RecordMetric.TIME,
        *,
        deduplicate: bool = True,
    ) -> tuple[Record, ...]:
        metric = RecordMetric(metric)
        html, url = await self._get("profile.php", {"pid": _id(player_id), "menu": int(metric)})
        return parse_records(html, player_id, metric, url, deduplicate=deduplicate)

    async def get_ranking(
        self,
        metric: RankingMetric = RankingMetric.TIME,
        *,
        source: str = "world",
        start: int = 0,
        sort: RankingSort = RankingSort.TOTAL,
    ) -> RankingPage:
        if source not in {"world", "arbiter"}:
            raise ValueError("source must be 'world' or 'arbiter'")
        metric, sort = RankingMetric(metric), RankingSort(sort)
        html, url = await self._get(
            f"common/ajax/ajax-ranking-{source}.php",
            {"rid": int(metric), "start": _start(start), "sort": int(sort)},
        )
        return parse_ranking(html, source, url, int(metric), start)

    async def get_density_ranking(
        self,
        board: DensityBoard = DensityBoard.WORLD,
        *,
        mines: int | None = None,
        start: int = 0,
        sort: int = 0,
    ) -> RankingPage:
        board = DensityBoard(board)
        if sort not in range(6):
            raise ValueError("density sort must be between 0 and 5")
        params = {"rid": int(board), "start": _start(start), "sort": sort}
        if mines is not None:
            params["mines"] = _id(mines, "mines")
        html, url = await self._get("common/ajax/ajax-ranking-density.php", params)
        return parse_ranking(html, "density", url, int(board), start)

    async def get_density_options(self, board: DensityBoard) -> tuple[Option, ...]:
        html, _ = await self._get(
            "common/ajax/ajax-ranking-density-menu-mines.php", {"rid": int(DensityBoard(board))}
        )
        return parse_options(html)

    async def get_countries(self) -> tuple[Option, ...]:
        html, _ = await self._get("country-rankings.php")
        return parse_options(html, "select[name=choose_country] option")

    async def get_country_regions(self, country_id: int) -> tuple[Option, ...]:
        html, _ = await self._get(
            "common/ajax/ajax-ranking-country-menu-states.php",
            {"cid": _id(country_id, "country_id")},
        )
        return parse_options(html)

    async def get_country_ranking(
        self,
        country_id: int,
        metric: RankingMetric = RankingMetric.TIME,
        *,
        region_id: int = 0,
        start: int = 0,
        sort: RankingSort = RankingSort.TOTAL,
    ) -> RankingPage:
        country_id, region_id = (
            _id(country_id, "country_id"),
            _id(region_id, "region_id", minimum=0),
        )
        metric, sort, start = RankingMetric(metric), RankingSort(sort), _start(start)
        async with self._lock:
            await self._fetch(
                BASE_URL + "common/ajax/ajax-ranking-country-menu-states.php", {"cid": country_id}
            )
            await self._fetch(
                BASE_URL + "common/ajax/ajax-ranking-country-menu-ranking.php", {"sid": region_id}
            )
            data, url, _ = await self._fetch(
                BASE_URL + "common/ajax/ajax-ranking-country.php",
                {"rid": int(metric), "start": start, "sort": int(sort)},
            )
        return parse_ranking(
            data.decode("utf-8", errors="replace"), "country", url, int(metric), start
        )

    async def get_historical_ranking(self, day: date | str, *, start: int = 0) -> RankingPage:
        day = date.fromisoformat(day) if isinstance(day, str) else day
        html, url = await self._get(
            "common/ajax/ajax-ranking-historical.php",
            {"did": day.isoformat(), "start": _start(start)},
        )
        return parse_ranking(html, "historical", url, start=start)

    async def get_world_records(self) -> tuple[WorldRecord, ...]:
        html, url = await self._get("world-records.php")
        return parse_world_records(html, url)

    async def download_replay(self, replay: Replay | str) -> bytes:
        url = replay.url if isinstance(replay, Replay) else replay
        async with self._lock:
            data, _, content_type = await self._fetch(url, replay=True)
        return _binary(data, content_type)
