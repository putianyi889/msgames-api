# API reference

Both `Client` and `AsyncClient` expose the same methods. Prefix calls with `await`
for the async client. Public parsing functions in `msgames_api.parsers` can also
parse HTML you already possess, without making requests.

## Client configuration and ownership

```python
Client(
    http_client=None,
    timeout=30,
    min_interval=1.0,
    max_page_bytes=8 * 1024 * 1024,
    max_replay_bytes=64 * 1024 * 1024,
)
```

`AsyncClient` accepts the same arguments with an `httpx.AsyncClient` as
`http_client`. An injected HTTP client is owned and closed by the caller; otherwise
the package creates and owns it. `close()` / `aclose()` are idempotent. Calls after
closure raise `RuntimeError`. Each async client belongs to one event loop.
Use a separate HTTP client for unrelated applications; cookie state participates
in the site's anonymous country/region selection. Sharing one HTTP client between
multiple package clients defeats their independent locks and pacing.

Requests are serialized and their start times are separated by `min_interval`
seconds. Multiple clients do not share a global rate limiter. No requests are
retried automatically. Async cancellation closes a response and releases the
request lock. Responses are streamed internally with limits on decoded bytes;
`download_replay` ultimately returns a bounded `bytes` object.

## Methods and request parameters

| Method | Inputs | Return |
| --- | --- | --- |
| `get_profile(player_id)` | positive `int`, bool rejected | `Profile` |
| `get_records(player_id, metric=RecordMetric.TIME, *, deduplicate=True)` | positive `int`; `RecordMetric`; `bool` | `tuple[Record, ...]` |
| `get_ranking(metric=RankingMetric.TIME, *, source="world", start=0, sort=RankingSort.TOTAL)` | `RankingMetric`; `"world"` or `"arbiter"`; offset `int`; `RankingSort` | `RankingPage` |
| `get_density_ranking(board=DensityBoard.WORLD, *, mines=None, start=0, sort=0)` | `DensityBoard`; positive `int \| None`; offset `int`; sort `int` 0–5 | `RankingPage` |
| `get_density_options(board)` | `DensityBoard` | `tuple[Option, ...]` |
| `get_countries()` | none | `tuple[Option, ...]` |
| `get_country_regions(country_id)` | positive `int` from `get_countries` | `tuple[Option, ...]` |
| `get_country_ranking(country_id, metric=RankingMetric.TIME, *, region_id=0, start=0, sort=RankingSort.TOTAL)` | positive country ID; `RankingMetric`; non-negative region ID; offset; `RankingSort` | `RankingPage` |
| `get_historical_ranking(day, *, start=0)` | `datetime.date \| str` in `YYYY-MM-DD` form; offset | `RankingPage` (experimental) |
| `get_world_records()` | none | `tuple[WorldRecord, ...]` |
| `download_replay(replay)` | `Replay \| str` public original-file URL | `bytes` |

Offsets are non-negative multiples of 100. There is no automatic pagination.
`RankingPage.next_start` suggests the next offset when 100 entries were returned;
a full final page may be followed by an empty page. Small leaderboards return all
their entries at once. `page_size` is 100. The library never enumerates player IDs.

Country rankings use three public requests in one locked operation: choose
country, choose region, read leaderboard. `region_id=0` means the whole country.
The server stores this selection in anonymous PHP session cookies.

```python
from msgames_api import Client, RankingMetric, DensityBoard

with Client() as api:
    countries = api.get_countries()
    china = next(c for c in countries if c.label == "China")
    regions = api.get_country_regions(china.value)
    ranking = api.get_country_ranking(china.value, RankingMetric.TIME_NF)
    mines = api.get_density_options(DensityBoard.EIGHT_BY_EIGHT)
    density = api.get_density_ranking(DensityBoard.EIGHT_BY_EIGHT, mines=mines[-1].value)
```

## Enum values

| Enum | Members and site values |
| --- | --- |
| `RecordMetric` | `TIME=2`, `THREE_BVS=3`, `IOE=4`, `DENSITY=5`, `PROBLEMS=6` |
| `RankingMetric` | `TIME=1`, `TIME_NF=2`, `THREE_BVS=3`, `THREE_BVS_NF=4`, `IOE=5` |
| `RankingSort` | `TOTAL=0`, `BEGINNER=1`, `INTERMEDIATE=2`, `EXPERT=3` |
| `DensityBoard` | `EIGHT_BY_EIGHT=1`, `NINE_BY_NINE=2`, `SIXTEEN_BY_SIXTEEN=3`, `THIRTY_BY_SIXTEEN=4`, `THIRTY_BY_TWENTY_FOUR=5`, `WORLD=6` |

Density sort 0 means total; 1–5 select the displayed board columns in world-density
ranking. For a single board, use sort 0. The values are taken from public frontend
controls, not an official server API specification.

## Response field types

All models are frozen dataclasses; their `fields` dictionaries remain mutable.
`to_dict()` returns JSON-compatible dictionaries: nested models become dictionaries,
tuples become lists, `Decimal` becomes a decimal string and `date` becomes ISO text.
`None` becomes JSON null. Nullable fields describe absent or unparseable displayed
data; they are not a promise about every page the website may ever return.

### Profile and profile links

| Fields | Python type | Evidence / meaning |
| --- | --- | --- |
| `player_id`, `url` | `int`, `str` | requested ID and fetched public URL |
| `name` | `str` | public Name cell; required by parser |
| `local_name`, `nickname`, `country`, `state`, `hand`, `mouse` | `str \| None` | named cells in public profile table |
| `joined` | `date \| None` | Joined cell, parsed as an ISO date |
| `fields` | `dict[str, str]` | all original profile labels and normalized text; unknown fields retained |
| `websites` | `tuple[Link, ...]` | public external links; never fetched by the client |
| `world_ranking`, `country_ranking` | `tuple[RankPosition, ...]` | public ranking cells |
| `Link.label`, `Link.url` | `str`, `str` | website label and absolute HTTP(S) link |
| `RankPosition.metric`, `.rank`, `.total` | `str`, `int`, `int` | displayed metric, rank, participant count; zero rank is retained |

Photo and biography data are excluded because the observed site requires login.

### Record and replay

| Fields | Python type | Evidence / meaning |
| --- | --- | --- |
| `player_id`, `metric` | `int`, `RecordMetric` | request context |
| `groups` | `tuple[str, ...]` | tab labels; examples: `expert`, `expert_nf`, `9x9`; Problems uses section headings |
| `level` | `str \| None` | `beginner`, `intermediate`, `expert` where explicit standard tabs exist |
| `date` | `date \| None` | Date column |
| `style` | `str \| None` | displayed style, e.g. FL or NF; NF can appear in the general tab too |
| `time`, `three_bvs`, `ioe` | `Decimal \| None` | Time, 3BVS, IOE columns; precision retained |
| `three_bv`, `mines` | `int \| None` | 3BV and Mines columns |
| `program`, `version`, `category`, `comment` | `str \| None` | displayed columns; Problems is retained as a category |
| `replay` | `Replay \| None` | public original download link; missing link remains null |
| `fields` | `dict[str, str]` | all original column names and text |
| `Replay.player_id` | `int \| None` | literal owner in public `parseVideo` call; null for direct world-record links |
| `Replay.filename`, `.url` | `str`, `str` | exact filename and absolute percent-encoded download URL |

The site duplicates NF records across general and NF tabs. Default deduplication
merges rows with the same replay URL and preserves all groups. Without a replay,
matching level and original column values are used. Set `deduplicate=False` to
retain displayed rows individually. Separate metric requests are never merged.
Records are the site's published score history, not every game a player played.
Normal empty score pages return `()`, including pages with no difficulty tabs or tables.
No statistic is inferred from a filename. Links use the public frontend's
`/member/file/{pid}/{filename}` template or a direct `/record/` anchor.

### Leaderboard page, entry and score

| Fields | Python type | Evidence / meaning |
| --- | --- | --- |
| `RankingPage.source`, `.url` | `str`, `str` | source name and fetched URL |
| `.ranking_id` | `int \| None` | requested metric/board ID; null for historical ranking |
| `.start`, `.page_size` | `int`, `int` | requested offset and 100-row page size |
| `.next_start` | `int \| None` | computed candidate offset; property, excluded from `to_dict()` |
| `.entries` | `tuple[RankingEntry, ...]` | displayed leaderboard rows |
| `RankingEntry.rank`, `.player_id` | `int`, `int \| None` | rank and linked profile ID; falls back to explicit replay owner |
| `.name`, `.country`, `.profile_url` | `str`, `str \| None`, `str \| None` | player name, flag filename slug (e.g. `china`), absolute profile link |
| `.scores`, `.total` | `tuple[Score, ...]`, `Decimal \| None` | board scores and displayed total |
| `.cells` | `tuple[str, ...]` | original normalized row cells, including empty layout cells |
| `Score.label`, `.value`, `.date`, `.replay` | `str`, `Decimal \| None`, `date \| None`, `Replay \| None` | displayed board label, metric value, date and original replay |

For world-density rankings the values are mine counts. For an individual density
board filtered by mines, the displayed values are times. The score label identifies
the board; `RankingPage.source`, `ranking_id` and request parameters supply context.
Arbiter leaderboard samples did not expose replay links; their score replay is null.
Country names in Profile are display names, whereas leaderboard country is a flag slug.

### Options and world-record history

| Fields | Python type | Evidence / meaning |
| --- | --- | --- |
| `Option.value`, `.label` | `int`, `str` | live dropdown values and labels; placeholder 0 omitted |
| `WorldRecord.section`, `.level` | `str`, `str \| None` | original section heading and recognized standard level |
| `.no_flags`, `.rejected` | `bool`, `bool` | NF and rejected markers in section heading |
| `.date_text`, `.date` | `str`, `date \| None` | original date preserved; partial dates such as 1997-00-00 have null parsed date |
| `.value` | `Decimal \| None` | displayed Time or 3BVS according to section heading |
| `.name`, `.country` | `str`, `str \| None` | original player name and flag slug |
| `.details`, `.comment` | `str`, `str` | accompanying text and rejection explanation |
| `.replay` | `Replay \| None` | direct publicly linked original file |

World-record history is an editorial historical list. It can lag current leaderboards;
the package preserves what each source actually displays.

## Failures

All package failures derive from `MsgamesError`:

| Exception | Meaning |
| --- | --- |
| `ParseError` | unexpected HTML, unsupported literal video call or invalid numeric data |
| `RequestError` | HTTPX transport failure (chained cause), or excessive redirects |
| `HTTPError` | unsuccessful status, with `status_code` and `url` |
| `NotFoundError` | HTTP 404, or an explicitly recognized missing-player message |
| `AccessDeniedError` | HTTP 401/403, login-only page or challenge page |
| `RateLimitError` | HTTP 429; `retry_after: str \| None` preserves header |
| `ResponseTooLargeError` | header or decoded response exceeds configured byte limit |
| `DownloadError` | original-file link returns HTML or an empty response |

Invalid arguments and off-site/unsafe replay links raise `ValueError` before
fetching. Redirects are checked before following. TLS verification is enabled.
Only HTTPS links on the site's host and recognized original replay directories are
accepted for downloads. No server-side video conversion endpoint is invoked.
