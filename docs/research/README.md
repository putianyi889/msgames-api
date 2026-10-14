# Public-source investigation — 2026-10-14

The repository started with only a license and Git configuration. Searches for
`minesweepergame.com python api profile scraper github`, exact-domain API and
scraper references did not identify a focused, maintained client suitable for
reuse. This is a limited search result, not a claim that no client exists.
Unrelated Minesweeper game-server libraries do not retrieve this site's data.

The implementation reuses [HTTPX](https://www.python-httpx.org/api/) for pooling,
cookies, timeouts, TLS and sync/async streaming, and
[Beautiful Soup](https://beautiful-soup-4.readthedocs.io/en/latest/) for HTML parsing.
The site-specific layer is small literal parsing and typed normalization. It
executes no JavaScript. Unknown `parseVideo` syntax fails explicitly.

## Evidence and boundaries

Sources were ordinary anonymous GET requests to the
[homepage](https://minesweepergame.com/),
[example profile](https://minesweepergame.com/profile.php?pid=7872),
[world rankings](https://minesweepergame.com/world-rankings.php),
[country rankings](https://minesweepergame.com/country-rankings.php),
[density rankings](https://minesweepergame.com/density-rankings.php),
[Arbiter rankings](https://minesweepergame.com/arbiter-rankings.php), and
[world-record history](https://minesweepergame.com/world-records.php).
Additional endpoint URLs came from inline scripts in these pages, without probing
unlinked routes. No authentication, vulnerability testing, directory enumeration,
ID scanning, injections or technical access-control bypass was used.

The site's [robots.txt](https://minesweepergame.com/robots.txt) restricts crawling of
`/profile.php`, `/member/`, `/record/`, `/common/` and several other directories,
and specifically blocks AI crawlers. The search browser declined access under
these rules. Public file accessibility is distinct from permission to crawl.
The package exposes deliberate individual reads and does not implement bulk crawling;
users must confirm permission for their intended collection. Default request
pacing is one second per client; HTTP failures and access challenges are not retried.

Biography (`menu=1`) returned a login requirement; the profile also explicitly
requires login for pictures. These are excluded. The profile's public Name, Local
Name, Nickname, Country, State, Joined, Hand and Mouse cells, external website link
and world/country rank positions were observed directly. Unknown labels are retained.

## Public request map

| Data | Public request / frontend evidence | Status |
| --- | --- | --- |
| Profile | `/profile.php?pid={id}` | verified |
| Score histories | same path, `menu=2/3/4/5/6` | all five categories verified |
| Original player replay | `/member/file/{pid}/{filename}`; constructed by public `parseVideo` function | one AVF downloaded; others only linked |
| World / Arbiter ranking | `/common/ajax/ajax-ranking-world.php` / `ajax-ranking-arbiter.php`; `rid,start,sort` | verified |
| Country dropdown | `/country-rankings.php` | verified |
| Country regions | `/common/ajax/ajax-ranking-country-menu-states.php?cid={id}` | verified |
| Country selection | `/common/ajax/ajax-ranking-country-menu-ranking.php?sid={id}` | verified in anonymous cookie session |
| Country ranking | `/common/ajax/ajax-ranking-country.php?rid={metric}&start={offset}&sort={sort}` | verified; country/region in anonymous session |
| Density mine options | `/common/ajax/ajax-ranking-density-menu-mines.php?rid={board}` | verified |
| Density ranking | `/common/ajax/ajax-ranking-density.php`; `rid,start,sort`, optional `mines` | world and one filtered board verified |
| World records | `/world-records.php`; direct `record/...` anchors | verified; original editorial headings retained |
| Historical ranking | `/common/ajax/ajax-ranking-historical.php?did={ISO-date}&start={offset}` | frontend observed; request for 2026-10-13 returned HTTP 500; experimental |

The AJAX session helper exists for browser pagination state, but the client uses
explicit offsets and sort values instead of querying arbitrary session keys.
The browser's `ajax-parse-video-for-video-player.php` converts a file into temporary
playback data; this package downloads the original publicly linked file and does
not invoke conversion. The Statistics page contains explanatory formulas rather
than an additional observed player dataset, so no speculative data endpoint was added.

## Parsing observations

- Score tables use `<td>` headers rather than `<th>`. Standard difficulty and NF
  variants are separate tabs. Identical NF replays occur in two tabs.
- Density tabs label explicit board dimensions. Problems uses section headings.
- Several leaderboard rows have unclosed `<tr>` tags and blank colspan layout rows.
  Parsing uses each row's direct cells so nested rows do not contaminate data.
- World-density tables have five score/date pairs; standard rankings have three.
  Individual filtered density rankings use an eight-cell layout with a blank header.
- A world-record row omits its trailing comment cell. Some dates include unknown
  month/day `00`; preserve original text and return null for the parsed date.
- The latest value in the editorial world-record list may differ from current
  ranking data. Neither source is silently corrected using the other.
- UTF-8 decoding is explicit; numeric values use Decimal and comma decimal
  separators are normalized. Non-finite/invalid numbers are rejected.

Offline fixtures use synthetic names and values while preserving these observed
structures. Full source pages and replay files are not redistributed. The
machine-readable [source manifest](sources.json) records page hashes and sample
scope. [Live validation](live-validation.json) records counts and hashes rather
than publishing player datasets; a source hash identifies the reviewed sample,
not a permanent site version.

No official stable JSON API contract was identified in the reviewed pages.
This client should be maintained against fresh authorized public samples whenever
page layout changes. Run `python tools/verify_live.py` explicitly to check the
supported read paths; network validation is excluded from CI.
