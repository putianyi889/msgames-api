"""Typed API for public MinesweeperGame.com data."""

from .client import AsyncClient, Client
from .exceptions import (
    AccessDeniedError,
    DownloadError,
    HTTPError,
    MsgamesError,
    NotFoundError,
    ParseError,
    RateLimitError,
    RequestError,
    ResponseTooLargeError,
)
from .models import (
    DensityBoard,
    Link,
    Option,
    Profile,
    RankingEntry,
    RankingMetric,
    RankingPage,
    RankingSort,
    RankPosition,
    Record,
    RecordMetric,
    Replay,
    Score,
    WorldRecord,
)

__version__ = "0.1.1"
__all__ = [
    "AccessDeniedError",
    "AsyncClient",
    "Client",
    "DensityBoard",
    "DownloadError",
    "HTTPError",
    "Link",
    "MsgamesError",
    "NotFoundError",
    "Option",
    "ParseError",
    "Profile",
    "RankPosition",
    "RankingEntry",
    "RankingMetric",
    "RankingPage",
    "RankingSort",
    "RateLimitError",
    "Record",
    "RecordMetric",
    "Replay",
    "RequestError",
    "ResponseTooLargeError",
    "Score",
    "WorldRecord",
]
