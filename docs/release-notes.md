# msgames-api 0.1.0

Initial release of the unofficial, typed Python client for public MinesweeperGame.com data.

- Python 3.11+, synchronous `Client` and asynchronous `AsyncClient`.
- Public player fields, world/country rank positions and five score-history categories.
- Original replay links and bounded downloads; Decimal values and JSON output.
- World, Arbiter, country/region and density leaderboards, options and explicit pagination.
- World-record history, including rejected records; experimental historical ranking entry point.
- CLI, field-level API reference, source investigation and live validation report.

Validation: 85 offline tests, Ruff, mypy, actionlint, package metadata checks,
live profile/score/leaderboard reads and an original replay download.
Historical ranking returned HTTP 500 during investigation and is marked experimental.
Photo/biography data requires login and is excluded.

The client only uses public GET requests and does not implement account enumeration
or bulk crawling. Default pacing is one request per second. The site's robots.txt
restricts crawling of relevant paths; confirm your intended use before collecting data at scale.

Install:

```sh
python -m pip install "https://github.com/putianyi889/msgames-api/releases/download/v0.1.0/msgames_api-0.1.0-py3-none-any.whl"
```

Assets include a wheel, source archive, Markdown documentation archive and SHA256SUMS.

[API reference](https://github.com/putianyi889/msgames-api/blob/v0.1.0/docs/api.md)
