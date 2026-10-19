import asyncio
import gzip
import time

import httpx
import pytest

from msgames_api import (
    AccessDeniedError,
    AsyncClient,
    Client,
    DensityBoard,
    DownloadError,
    HTTPError,
    NotFoundError,
    RateLimitError,
    RecordMetric,
    RequestError,
    ResponseTooLargeError,
)

from .conftest import EMPTY_RECORDS, OPTIONS, PROFILE, RANKING, RECORDS, WORLD_RECORDS

REPLAY_URL = "https://minesweepergame.com/member/file/42/test.avf"


def handler(request):
    path = request.url.path
    if path == "/profile.php":
        body = RECORDS if "menu" in request.url.params else PROFILE
    elif path.endswith("world-records.php"):
        body = WORLD_RECORDS
    elif path.endswith("country-rankings.php"):
        body = f"<select name=choose_country>{OPTIONS}</select>"
    elif "menu-" in path:
        body = OPTIONS
    elif "ajax-ranking-" in path:
        body = RANKING
    elif path.endswith(".avf"):
        return httpx.Response(200, content=b"\x34\x0f\x01binary replay")
    else:
        raise AssertionError(path)
    return httpx.Response(200, text=body)


OPERATIONS = [
    ("get_profile", (42,), {}),
    ("get_records", (42,), {}),
    ("get_ranking", (), {}),
    ("get_ranking", (), {"source": "arbiter"}),
    ("get_density_ranking", (), {}),
    ("get_density_options", (DensityBoard.EIGHT_BY_EIGHT,), {}),
    ("get_countries", (), {}),
    ("get_country_regions", (36,), {}),
    ("get_country_ranking", (36,), {}),
    ("get_historical_ranking", ("2024-01-02",), {}),
    ("get_world_records", (), {}),
    ("download_replay", (REPLAY_URL,), {}),
]


@pytest.mark.parametrize("method,args,kwargs", OPERATIONS)
def test_sync_public_api(method, args, kwargs):
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        with Client(http_client=http, min_interval=0) as client:
            assert getattr(client, method)(*args, **kwargs)
        assert not http.is_closed


@pytest.mark.parametrize("method,args,kwargs", OPERATIONS)
async def test_async_public_api(method, args, kwargs):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        async with AsyncClient(http_client=http, min_interval=0) as client:
            assert await getattr(client, method)(*args, **kwargs)
        assert not http.is_closed


async def test_empty_problems_page_in_both_clients():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=EMPTY_RECORDS))
    with httpx.Client(transport=transport) as http:
        with Client(http_client=http, min_interval=0) as client:
            assert client.get_records(7714, RecordMetric.PROBLEMS) == ()
    async with httpx.AsyncClient(transport=transport) as http:
        async with AsyncClient(http_client=http, min_interval=0) as client:
            assert await client.get_records(7714, RecordMetric.PROBLEMS) == ()


@pytest.mark.parametrize(
    "status,error",
    [
        (404, NotFoundError),
        (403, AccessDeniedError),
        (401, AccessDeniedError),
        (429, RateLimitError),
        (500, HTTPError),
    ],
)
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_http_failures_without_retries(status, error, asynchronous):
    calls = []

    def failure(request):
        calls.append(request)
        return httpx.Response(status, headers={"Retry-After": "60"})

    if asynchronous:
        async with httpx.AsyncClient(transport=httpx.MockTransport(failure)) as http:
            async with AsyncClient(http_client=http, min_interval=0) as client:
                with pytest.raises(error) as caught:
                    await client.get_profile(42)
    else:
        with httpx.Client(transport=httpx.MockTransport(failure)) as http:
            with Client(http_client=http, min_interval=0) as client:
                with pytest.raises(error) as caught:
                    client.get_profile(42)
    assert len(calls) == 1
    if status == 429:
        assert caught.value.retry_after == "60"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.org/test.avf",
        "http://minesweepergame.com/record/test.avf",
        "https://minesweepergame.com/admin/test.avf",
        "https://user:pass@minesweepergame.com/record/test.avf",
        "https://minesweepergame.com/member/file/42/%252e%252e/test.avf",
        "https://minesweepergame.com:8443/record/test.avf",
    ],
)
async def test_replay_urls_are_validated_in_both_clients(url):
    with Client(min_interval=0) as client:
        with pytest.raises(ValueError):
            client.download_replay(url)
    async with AsyncClient(min_interval=0) as client:
        with pytest.raises(ValueError):
            await client.download_replay(url)


@pytest.mark.parametrize("asynchronous", [False, True])
async def test_redirect_is_checked_before_following(asynchronous):
    calls = []

    def redirect(request):
        calls.append(request)
        return httpx.Response(302, headers={"Location": "https://example.org/record/test.avf"})

    if asynchronous:
        async with httpx.AsyncClient(transport=httpx.MockTransport(redirect)) as http:
            async with AsyncClient(http_client=http, min_interval=0) as client:
                with pytest.raises(ValueError):
                    await client.download_replay(REPLAY_URL)
    else:
        with httpx.Client(transport=httpx.MockTransport(redirect)) as http:
            with Client(http_client=http, min_interval=0) as client:
                with pytest.raises(ValueError):
                    client.download_replay(REPLAY_URL)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "content,content_type",
    [
        (b"", "application/octet-stream"),
        (b"<!doctype html><html>login</html>", "text/plain"),
        (b"some data", "text/html"),
    ],
)
async def test_html_and_empty_downloads_fail(content, content_type):
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, content=content, headers={"content-type": content_type})
    )
    with httpx.Client(transport=transport) as http:
        with Client(http_client=http, min_interval=0) as client:
            with pytest.raises(DownloadError):
                client.download_replay(REPLAY_URL)
    async with httpx.AsyncClient(transport=transport) as http:
        async with AsyncClient(http_client=http, min_interval=0) as client:
            with pytest.raises(DownloadError):
                await client.download_replay(REPLAY_URL)


async def test_decoded_size_limit_in_both_clients():
    transport = httpx.MockTransport(
        lambda r: httpx.Response(
            200, content=gzip.compress(b"x" * 4096), headers={"content-encoding": "gzip"}
        )
    )
    with httpx.Client(transport=transport) as http:
        with Client(http_client=http, min_interval=0, max_page_bytes=100) as client:
            with pytest.raises(ResponseTooLargeError):
                client.get_profile(42)
    async with httpx.AsyncClient(transport=transport) as http:
        async with AsyncClient(http_client=http, min_interval=0, max_page_bytes=100) as client:
            with pytest.raises(ResponseTooLargeError):
                await client.get_profile(42)


async def test_country_context_cannot_interleave():
    calls = []

    async def delayed(request):
        calls.append((request.url.path, dict(request.url.params)))
        await asyncio.sleep(0)
        return handler(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(delayed)) as http:
        async with AsyncClient(http_client=http, min_interval=0) as client:
            await asyncio.gather(client.get_country_ranking(36), client.get_country_ranking(9))
    assert [query.get("cid") for _, query in calls[::3]] == ["36", "9"]
    assert all("menu-states" in calls[i][0] for i in (0, 3))
    assert all("menu-ranking" in calls[i][0] for i in (1, 4))


async def test_pacing_with_concurrent_calls():
    starts = []

    def timed(request):
        starts.append(time.monotonic())
        return handler(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(timed)) as http:
        async with AsyncClient(http_client=http, min_interval=0.02) as client:
            await asyncio.gather(*(client.get_profile(42) for _ in range(3)))
    assert all(b - a >= 0.018 for a, b in zip(starts, starts[1:], strict=False))


async def test_cancellation_closes_response_and_releases_lock():
    started, closed = asyncio.Event(), asyncio.Event()

    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"initial"
            started.set()
            await asyncio.Event().wait()

        async def aclose(self):
            closed.set()

    def respond(request):
        return (
            httpx.Response(200, stream=SlowStream())
            if request.url.path.endswith(".avf")
            else handler(request)
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        async with AsyncClient(http_client=http, min_interval=0) as client:
            task = asyncio.create_task(client.download_replay(REPLAY_URL))
            await asyncio.wait_for(started.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert closed.is_set()
            assert (await client.get_profile(42)).name == "Test Player"


async def test_owned_clients_close_and_cannot_be_reused():
    sync = Client()
    sync.close()
    sync.close()
    assert sync._http.is_closed
    with pytest.raises(RuntimeError):
        sync.get_profile(42)
    client = AsyncClient()
    await client.aclose()
    await client.aclose()
    assert client._http.is_closed
    with pytest.raises(RuntimeError):
        await client.get_profile(42)


@pytest.mark.parametrize("player_id", [True, 0, -1, "42", 1.5])
async def test_invalid_ids_fail_before_requests(player_id):
    with Client() as client:
        with pytest.raises(ValueError):
            client.get_profile(player_id)
    async with AsyncClient() as client:
        with pytest.raises(ValueError):
            await client.get_profile(player_id)


def test_invalid_parameters():
    with Client() as client:
        with pytest.raises(ValueError):
            client.get_ranking(start=1)
        with pytest.raises(ValueError):
            client.get_ranking(source="admin")
        with pytest.raises(ValueError):
            client.get_records(42, 7)
        with pytest.raises(ValueError):
            client.get_density_ranking(sort=6)


async def test_transport_errors_are_chained():
    def failed(request):
        raise httpx.ConnectError("Connection failed", request=request)

    transport = httpx.MockTransport(failed)
    with httpx.Client(transport=transport) as http:
        with Client(http_client=http, min_interval=0) as client:
            with pytest.raises(RequestError) as caught:
                client.get_profile(42)
            assert isinstance(caught.value.__cause__, httpx.ConnectError)
    async with httpx.AsyncClient(transport=transport) as http:
        async with AsyncClient(http_client=http, min_interval=0) as client:
            with pytest.raises(RequestError) as caught:
                await client.get_profile(42)
            assert isinstance(caught.value.__cause__, httpx.ConnectError)
