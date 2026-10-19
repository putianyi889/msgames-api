# msgames-api 0.1.1

Fix normal empty score pages being reported as parsing errors.

- `get_records()` now returns `()` when the site's normal score-content area is empty,
  even if the page omits difficulty tabs and score tables. This fixes player 7714's
  Problems page and applies to both synchronous and asynchronous clients.
- Nonempty unrecognized pages and missing content structures still raise `ParseError`.
- Added regression coverage for all five record categories, both deduplication modes,
  sync/async clients, and malformed or error pages. Updated the API reference.

Validation: 102 offline tests, Ruff, mypy, and the public HTML of player 7714's Problems page.

Install:

```sh
python -m pip install "https://github.com/putianyi889/msgames-api/releases/download/v0.1.1/msgames_api-0.1.1-py3-none-any.whl"
```

Assets include a wheel, source archive, Markdown documentation archive and SHA256SUMS.

[API reference](https://github.com/putianyi889/msgames-api/blob/v0.1.1/docs/api.md)
