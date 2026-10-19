"""Pure HTML parsers, also usable with independently acquired public HTML."""

import re
from dataclasses import replace
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from .exceptions import AccessDeniedError, NotFoundError, ParseError
from .models import (
    Link,
    Option,
    Profile,
    RankingEntry,
    RankingPage,
    RankPosition,
    Record,
    RecordMetric,
    Replay,
    Score,
    WorldRecord,
)

BASE_URL = "https://minesweepergame.com/"
REPLAY_EXTENSIONS = {".avf", ".mvf", ".mvr", ".rmv"}
_CALL = re.compile(r"^\s*parseVideo\(\s*(['\"])(\d+)\1\s*,\s*(['\"])([^'\"\r\n]+)\3\s*\)\s*;?\s*$")
_LEVELS = {"b": "beginner", "i": "intermediate", "e": "expert"}


def _soup(html: str) -> BeautifulSoup:
    # Text decoding happens explicitly in the transport. Do not let charset detection
    # reinterpret UTF-8 Chinese names as legacy encodings.
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".msgame-content") or soup
    text = content.get_text(" ", strip=True).lower()
    if soup.select_one("#profile table") is None and re.search(
        r"(?:please\s+)?log\s*in\s+to\s+(?:view|see)", text
    ):
        raise AccessDeniedError("This page requires login")
    if any(message in text for message in ("access denied", "verify you are human", "captcha")):
        raise AccessDeniedError("The server denied automated access")
    return soup


def _text(tag: Tag) -> str:
    return " ".join(tag.get_text(" ", strip=True).split())


def _cells(row: Tag) -> list[Tag]:
    return row.find_all(["td", "th"], recursive=False)


def _decimal(text: str) -> Decimal | None:
    if text.strip() in {"", "-", "N/A"}:
        return None
    try:
        value = Decimal(text.strip().replace(",", "."))
        if not value.is_finite():
            raise InvalidOperation
        return value
    except InvalidOperation as exc:
        raise ParseError(f"Invalid numeric value: {text!r}") from exc


def _integer(text: str) -> int | None:
    value = _decimal(text)
    if value is None:
        return None
    if value != value.to_integral_value():
        raise ParseError(f"Invalid integer: {text!r}")
    return int(value)


def _date(text: str) -> date | None:
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _country(row: Tag) -> str | None:
    images = [image for cell in (_cells(row) or [row]) for image in cell.select("img[src]")]
    for image in images:
        path = urlsplit(str(image["src"])).path
        if "/flags/" in path:
            return unquote(path.rsplit("/", 1)[-1].rsplit(".", 1)[0])
    return None


def _replay(row: Tag, url: str) -> Replay | None:
    for anchor in row.select("a"):
        onclick = str(anchor.get("onclick", ""))
        match = _CALL.fullmatch(onclick)
        if match:
            player_id, filename = int(match[2]), match[4]
            if any(char in filename for char in ("/", "\\", "\x00")) or filename in {".", ".."}:
                raise ParseError("Unsafe replay filename in public HTML")
            suffix = "." + filename.rsplit(".", 1)[-1].lower()
            if suffix not in REPLAY_EXTENSIONS:
                raise ParseError(f"Unsupported replay extension: {suffix}")
            return Replay(
                player_id,
                filename,
                urljoin(BASE_URL, f"member/file/{player_id}/{quote(filename, safe='')}"),
            )
        if "parseVideo" in onclick:
            raise ParseError("Unsupported parseVideo syntax; no JavaScript is executed")
        href = str(anchor.get("href", ""))
        path = urlsplit(href).path
        if any(path.lower().endswith(ext) for ext in REPLAY_EXTENSIONS):
            return Replay(None, unquote(path.rsplit("/", 1)[-1]), urljoin(url, href))
    return None


def parse_profile(html: str, player_id: int, url: str | None = None) -> Profile:
    url = url or f"{BASE_URL}profile.php?pid={player_id}"
    soup = _soup(html)
    table = soup.select_one("#profile table")
    if table is None:
        text = soup.get_text(" ", strip=True).lower()
        if any(s in text for s in ("not found", "does not exist", "invalid player")):
            raise NotFoundError(404, url)
        raise ParseError("Missing #profile table")
    fields: dict[str, str] = {}
    for row in table.find_all("tr"):
        cells = _cells(row)
        if len(cells) == 2:
            fields[_text(cells[0])] = _text(cells[1])
    if not fields.get("Name"):
        raise ParseError("Missing public player name")
    websites = []
    for row in soup.select("#sites tr"):
        cells = _cells(row)
        if len(cells) == 2:
            for anchor in cells[1].select("a[href]"):
                href = urljoin(url, str(anchor["href"]))
                if urlsplit(href).scheme in {"http", "https"}:
                    websites.append(Link(_text(cells[0]) or _text(anchor), href))

    def ranks(section: str) -> tuple[RankPosition, ...]:
        result = []
        for row in soup.select(f"#{section} tr"):
            cells = _cells(row)
            if len(cells) != 4:
                raise ParseError(f"Unexpected {section} ranking row")
            rank, total = _integer(_text(cells[1])), _integer(_text(cells[3]))
            if rank is None or total is None:
                raise ParseError("Missing ranking position")
            result.append(RankPosition(_text(cells[0]), rank, total))
        return tuple(result)

    return Profile(
        player_id,
        url,
        fields["Name"],
        fields.get("Local Name") or None,
        fields.get("Nickname") or None,
        fields.get("Country") or None,
        fields.get("State") or None,
        _date(fields.get("Joined", "")),
        fields.get("Hand") or None,
        fields.get("Mouse") or None,
        fields,
        tuple(websites),
        ranks("world"),
        ranks("country"),
    )


def parse_records(
    html: str,
    player_id: int,
    metric: RecordMetric = RecordMetric.TIME,
    url: str | None = None,
    *,
    deduplicate: bool = True,
) -> tuple[Record, ...]:
    metric = RecordMetric(metric)
    url = url or f"{BASE_URL}profile.php?pid={player_id}&menu={int(metric)}"
    soup = _soup(html)
    records: list[Record] = []
    indices: dict[tuple[str, ...], int] = {}
    known_tables = 0
    group_labels = {
        str(a.get("href", "")).removeprefix("#"): _text(a) for a in soup.select(".nav-tabs a[href]")
    }
    for table in soup.select("table"):
        rows = [row for row in table.find_all("tr") if _cells(row)]
        if not rows:
            continue
        headers = [_text(c) for c in _cells(rows[0])]
        if not {"Date", "Style", "Time", "3BV"}.issubset(headers):
            continue
        known_tables += 1
        tab = table.find_parent(class_="tab-pane")
        tab_id = str(tab.get("id", "")) if tab else ""
        heading = table.find_previous(["h3", "h4", "h5"])
        group = tab_id.removeprefix("tab_") if tab else (_text(heading) if heading else "")
        group = _LEVELS.get(group, group)
        if group.endswith("_nf"):
            group = _LEVELS.get(group[:-3], group[:-3]) + "_nf"
        if metric == RecordMetric.DENSITY:
            group = group_labels.get(tab_id, group)
        level = group.removesuffix("_nf") if group.removesuffix("_nf") in _LEVELS.values() else None
        for row in rows[1:]:
            cells = _cells(row)
            if len(cells) != len(headers):
                raise ParseError("Record column count changed")
            fields = dict(zip(headers, map(_text, cells), strict=True))
            replay = _replay(row, url)
            record = Record(
                player_id,
                metric,
                (group,),
                level,
                _date(fields["Date"]),
                fields.get("Style") or None,
                _decimal(fields["Time"]),
                _integer(fields["3BV"]),
                _decimal(fields.get("3BVS", "")),
                _decimal(fields.get("IOE", "")),
                _integer(fields.get("Mines", "")),
                fields.get("Program") or None,
                fields.get("Version") or None,
                fields.get("Category") or None,
                fields.get("Comment") or None,
                replay,
                fields,
            )
            key = (replay.url,) if replay else (str(level), *fields.values())
            if deduplicate and key in indices:
                idx = indices[key]
                previous = records[idx]
                records[idx] = replace(
                    previous, groups=tuple(dict.fromkeys((*previous.groups, group)))
                )
            else:
                indices[key] = len(records)
                records.append(record)
    if not known_tables:
        # Empty score pages can omit both tables and difficulty tabs (e.g. Problems).
        content = soup.select_one(".msgame-content .col-sm-10")
        empty_content = (
            content is not None
            and not _text(content)
            and all(tag.name in {"div", "br", "script", "style"} for tag in content.find_all(True))
        )
        if not soup.select(".msgame-content .nav-tabs") and not empty_content:
            raise ParseError("Missing record tables and level tabs")
    return tuple(records)


def parse_options(html: str, selector: str = "option") -> tuple[Option, ...]:
    soup = _soup(html)
    options = []
    for tag in soup.select(selector):
        value = str(tag.get("value", ""))
        if value.isdecimal() and int(value) > 0:
            options.append(Option(int(value), _text(tag)))
    if not soup.select("option"):
        raise ParseError("Missing public dropdown options")
    return tuple(options)


def parse_ranking(
    html: str,
    source: str,
    url: str,
    ranking_id: int | None = None,
    start: int = 0,
) -> RankingPage:
    soup = _soup(html)
    table = soup.find("table")
    if table is None:
        raise ParseError("Missing ranking table")
    rows = [r for r in table.find_all("tr") if _cells(r) and _text(r)]
    # Empty layout rows can contain nested rows in this site's malformed HTML.
    rows = [r for r in rows if any(_text(c) for c in _cells(r))]
    if not rows:
        return RankingPage(source, url, ranking_id, start, ())
    header = _cells(rows[0])
    labels = [_text(cell) for cell in header[4:-1]]
    single_density = source == "density" and ranking_id != 6 and len(header) == 8
    if single_density:
        labels = [
            {1: "8x8", 2: "9x9", 3: "16x16", 4: "30x16", 5: "30x24"}.get(ranking_id or 0, "Density")
        ]
        # Individual density tables have a blank layout row, rather than headings.
        rows.insert(0, rows[0])
    if not labels:
        raise ParseError("Missing ranking score columns")
    entries = []
    for row in rows[1:]:
        cells = _cells(row)
        if len(cells) != (8 if single_density else 5 + 2 * len(labels)):
            raise ParseError("Ranking column count changed")
        rank = _integer(_text(cells[0]))
        if rank is None:
            raise ParseError("Missing ranking number")
        player_id = None
        profile_url = None
        for anchor in cells[1].select("a[href]"):
            candidate = urljoin(url, str(anchor["href"]))
            parts = urlsplit(candidate)
            pid = parse_qs(parts.query).get("pid", [""])[0]
            if parts.path == "/profile.php" and pid.isdecimal():
                player_id, profile_url = int(pid), candidate
        scores = tuple(
            Score(
                label,
                _decimal(_text(cells[4 + 2 * i])),
                _date(_text(cells[5 + 2 * i])),
                _replay(cells[4 + 2 * i], url),
            )
            for i, label in enumerate(labels)
        )
        if single_density:
            scores = (
                Score(
                    labels[0],
                    _decimal(_text(cells[4])),
                    _date(_text(cells[7])),
                    _replay(cells[4], url),
                ),
            )
        if player_id is None:
            player_id = next(
                (s.replay.player_id for s in scores if s.replay and s.replay.player_id), None
            )
            if player_id is not None:
                profile_url = f"{BASE_URL}profile.php?pid={player_id}"
        entries.append(
            RankingEntry(
                rank,
                player_id,
                _text(cells[2]),
                _country(row),
                profile_url,
                scores,
                _decimal(_text(cells[6] if single_density else cells[-1])),
                tuple(map(_text, cells)),
            )
        )
    return RankingPage(source, url, ranking_id, start, tuple(entries))


def parse_world_records(
    html: str, url: str = BASE_URL + "world-records.php"
) -> tuple[WorldRecord, ...]:
    soup = _soup(html)
    result = []
    for table in soup.select(".msgame-content table"):
        heading = table.find_previous(["h3", "h4", "h5"])
        if heading is None or "world records" not in _text(heading).lower():
            continue
        section = _text(heading)
        lower = section.lower()
        level = next((s for s in _LEVELS.values() if s in lower), None)
        for row in table.find_all("tr"):
            cells = _cells(row)
            if not cells:
                continue
            if len(cells) not in {5, 6}:
                raise ParseError("World record column count changed")
            date_text = _text(cells[0])
            result.append(
                WorldRecord(
                    section,
                    level,
                    " nf " in lower,
                    "rejected" in lower,
                    date_text,
                    _date(date_text),
                    _decimal(_text(cells[1])),
                    _text(cells[3]),
                    _country(row),
                    _text(cells[4]),
                    _text(cells[5]) if len(cells) == 6 else "",
                    _replay(cells[1], url),
                )
            )
    if not result:
        raise ParseError("Missing world record history tables")
    return tuple(result)
