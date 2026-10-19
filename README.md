# msgames-api

[![CI](https://github.com/putianyi889/msgames-api/actions/workflows/ci.yml/badge.svg)](https://github.com/putianyi889/msgames-api/actions/workflows/ci.yml)

获取 [MinesweeperGame.com](https://minesweepergame.com/) 公开数据的 Python 包。
支持 Python 3.11+，提供同步 `Client`、异步 `AsyncClient`、类型标注和 JSON 命令行。
这是非官方客户端：数据来自公开 HTML 和网页脚本明确调用的 GET 请求。

## 安装

从 [GitHub Releases](https://github.com/putianyi889/msgames-api/releases) 安装 wheel：

```sh
python -m pip install "https://github.com/putianyi889/msgames-api/releases/download/v0.1.1/msgames_api-0.1.1-py3-none-any.whl"
```

## 使用

```python
from pathlib import Path
from msgames_api import Client, RecordMetric

with Client() as api:
    profile = api.get_profile(7872)
    print(profile.name, profile.local_name, profile.country)
    print(profile.to_dict())

    records = api.get_records(7872, RecordMetric.TIME)
    for record in records:
        print(record.date, record.time, record.three_bv)
        if record.replay:
            print(record.replay.url)

    replay = next(r.replay for r in records if r.replay)
    # 文件名由调用方选择，避免覆盖已有文件。
    with Path("replay.avf").open("xb") as file:
        file.write(api.download_replay(replay))

    ranking = api.get_ranking()
    print(ranking.entries[0].name, ranking.entries[0].total)
```

```python
import asyncio
from msgames_api import AsyncClient, RecordMetric


async def main():
    async with AsyncClient() as api:
        profile = await api.get_profile(7872)
        records = await api.get_records(7872, RecordMetric.THREE_BVS)
        print(profile.name, len(records))


asyncio.run(main())
```

支持的数据：

- 用户姓名、本地姓名、昵称、国家、地区、加入日期、惯用手、鼠标、外部网站，以及世界／国家排名。
- Time、3BVS、IOE、Density、Problems 五类公开成绩；保留日期、风格、统计值、程序、版本、类别和备注。
- 页面展示的 AVF／MVF／MVR／RMV 原始录像链接与下载；不解析录像格式。
- 世界、Arbiter、国家／地区、密度排行榜，国家／地区／雷数选项和显式分页。
- 世界纪录历史，包括被拒绝的成绩及其说明。
- 历史世界排名入口为实验性功能；调查中的公开请求返回 HTTP 500，不能保证服务端可用。

```sh
msgames-api profile 7872
msgames-api records 7872 --metric three_bvs
msgames-api ranking --source world --metric 1 --start 100
msgames-api world-records
```

详细的参数、返回字段类型、异常和分页说明见 [API 文档](docs/api.md)；
数据来源、网站限制和实时验证范围见 [调查报告](docs/research/README.md)。

## 获取约定

客户端只执行公开 GET，不提供登录、上传、修改、用户 ID 扫描或全站爬取。
默认每个客户端的请求开始时间间隔至少 1 秒，并串行访问以维护匿名会话。
网站 [robots.txt](https://minesweepergame.com/robots.txt) 将 `/profile.php`、`/member/`、
`/record/`、`/common/` 等列为禁止爬虫抓取路径，也单独限制 AI 爬虫。
直接可访问不代表允许批量采集；使用者需要自行确认网站允许的使用范围。
需要登录的照片和传记不属于本包的数据范围。

网页结构变化会影响解析。未知页面布局抛出 `ParseError`；HTTP 429 保留 `Retry-After`，
客户端不会自动重试。数值使用 `Decimal`，`to_dict()` 将数值小数和日期转换为字符串，
保留显示精度。数据版权属于原网站／贡献者，MIT 许可证仅适用于本包代码。

## 开发与发布

```sh
python -m venv .venv
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest --cov=msgames_api
python -m build
python -m twine check dist/*
```

离线测试使用合成 HTML 和 HTTPX MockTransport，不访问网站。
实时验证需手动运行 `python tools/verify_live.py`，默认会执行少量公开请求。
CI 覆盖 Ubuntu Python 3.11–3.14 和 Windows Python 3.14。
推送与包版本匹配的 `vX.Y.Z` 标签会发布 GitHub Release，附 wheel、sdist、文档和 SHA-256 校验文件。
发布不涉及 PyPI。

## English

A typed, unofficial Python client for public MinesweeperGame.com data, supporting
synchronous and asynchronous requests, player profiles, score histories, replay
links/downloads, world/Arbiter/country/density leaderboards and world-record history.
Install the wheel from GitHub Releases using the command above. See the examples
and [API reference](docs/api.md) for all methods and response fields.

Only publicly linked GET resources are supported. No authentication, uploads,
account enumeration or automatic crawling is implemented. The site restricts
crawling of several relevant paths in its robots.txt; confirm your intended use
with the site owner before collecting data at scale. Requests are paced at one
per second by default. Historical rankings are experimental because the observed
server request failed with HTTP 500. HTML changes raise explicit parsing errors.
