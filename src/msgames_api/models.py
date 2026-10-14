"""Public data models. Decimal values retain the precision displayed by the site."""

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from enum import IntEnum
from typing import Any


class RecordMetric(IntEnum):
    TIME = 2
    THREE_BVS = 3
    IOE = 4
    DENSITY = 5
    PROBLEMS = 6


class RankingMetric(IntEnum):
    TIME = 1
    TIME_NF = 2
    THREE_BVS = 3
    THREE_BVS_NF = 4
    IOE = 5


class RankingSort(IntEnum):
    TOTAL = 0
    BEGINNER = 1
    INTERMEDIATE = 2
    EXPERT = 3


class DensityBoard(IntEnum):
    EIGHT_BY_EIGHT = 1
    NINE_BY_NINE = 2
    SIXTEEN_BY_SIXTEEN = 3
    THIRTY_BY_SIXTEEN = 4
    THIRTY_BY_TWENTY_FOUR = 5
    WORLD = 6


def _json(value: Any) -> Any:
    if isinstance(value, (Decimal, date)):
        return str(value)
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


class Model:
    def to_dict(self) -> dict[str, Any]:
        """JSON-compatible representation; dates and decimals become strings."""
        return _json(asdict(self))  # type: ignore[call-overload,no-any-return]


@dataclass(frozen=True)
class Link(Model):
    label: str
    url: str


@dataclass(frozen=True)
class RankPosition(Model):
    metric: str
    rank: int
    total: int


@dataclass(frozen=True)
class Profile(Model):
    player_id: int
    url: str
    name: str
    local_name: str | None
    nickname: str | None
    country: str | None
    state: str | None
    joined: date | None
    hand: str | None
    mouse: str | None
    fields: dict[str, str]
    websites: tuple[Link, ...]
    world_ranking: tuple[RankPosition, ...]
    country_ranking: tuple[RankPosition, ...]


@dataclass(frozen=True)
class Replay(Model):
    player_id: int | None
    filename: str
    url: str


@dataclass(frozen=True)
class Record(Model):
    player_id: int
    metric: RecordMetric
    groups: tuple[str, ...]
    level: str | None
    date: date | None
    style: str | None
    time: Decimal | None
    three_bv: int | None
    three_bvs: Decimal | None
    ioe: Decimal | None
    mines: int | None
    program: str | None
    version: str | None
    category: str | None
    comment: str | None
    replay: Replay | None
    fields: dict[str, str]


@dataclass(frozen=True)
class Score(Model):
    label: str
    value: Decimal | None
    date: date | None
    replay: Replay | None


@dataclass(frozen=True)
class RankingEntry(Model):
    rank: int
    player_id: int | None
    name: str
    country: str | None
    profile_url: str | None
    scores: tuple[Score, ...]
    total: Decimal | None
    cells: tuple[str, ...]


@dataclass(frozen=True)
class RankingPage(Model):
    source: str
    url: str
    ranking_id: int | None
    start: int
    entries: tuple[RankingEntry, ...]
    page_size: int = 100

    @property
    def next_start(self) -> int | None:
        """Candidate offset; a full last page can still be followed by an empty page."""
        return self.start + self.page_size if len(self.entries) == self.page_size else None


@dataclass(frozen=True)
class Option(Model):
    value: int
    label: str


@dataclass(frozen=True)
class WorldRecord(Model):
    section: str
    level: str | None
    no_flags: bool
    rejected: bool
    date_text: str
    date: date | None
    value: Decimal | None
    name: str
    country: str | None
    details: str
    comment: str
    replay: Replay | None
