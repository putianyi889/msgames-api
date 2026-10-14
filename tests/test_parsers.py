import json
from datetime import date
from decimal import Decimal

import pytest

from msgames_api import AccessDeniedError, NotFoundError, ParseError, RecordMetric
from msgames_api.parsers import (
    parse_options,
    parse_profile,
    parse_ranking,
    parse_records,
    parse_world_records,
)

from .conftest import OPTIONS, RECORD_ROW, WORLD_RECORDS


def test_profile_unicode_links_and_unknown_fields(profile_html):
    profile = parse_profile(profile_html, 42)
    assert profile.local_name == "测试玩家"
    assert profile.nickname == "A & B"
    assert profile.mouse is None
    assert profile.state is None
    assert profile.joined == date(2020, 2, 29)
    assert profile.fields["New Field"] == "preserved"
    assert profile.world_ranking[0].rank == 0
    assert profile.websites[0].url == "https://example.org/player?id=42&lang=en"
    assert profile.to_dict()["joined"] == "2020-02-29"


def test_login_page_and_not_found():
    with pytest.raises(AccessDeniedError):
        parse_profile("<p>Please log in to view player biographies.</p>", 42)
    with pytest.raises(NotFoundError):
        parse_profile("Player not found", 42)
    with pytest.raises(ParseError):
        parse_profile("<div id=profile><table></table></div>", 42)


def test_records_precision_deduplication_and_groups(records_html):
    records = parse_records(records_html, 42)
    assert len(records) == 1
    record = records[0]
    assert record.groups == ("beginner", "beginner_nf")
    assert record.level == "beginner"
    assert record.style == "NF"
    assert record.time == Decimal("0.490")
    assert record.comment == "Test & comment"
    assert record.replay.filename == "42-Time-88-NF-0,490-3.avf"
    assert "%2C" in record.replay.url
    assert record.to_dict()["time"] == "0.490"
    assert '"metric": 2' in json.dumps(record.to_dict())
    assert len(parse_records(records_html, 42, deduplicate=False)) == 2


@pytest.mark.parametrize(
    "metric,column,value,attribute",
    [
        (RecordMetric.THREE_BVS, "3BVS", "6.122", "three_bvs"),
        (RecordMetric.IOE, "IOE", "1.234", "ioe"),
        (RecordMetric.DENSITY, "Mines", "28", "mines"),
        (RecordMetric.PROBLEMS, "3BVS", "6.122", "three_bvs"),
    ],
)
def test_other_record_metrics(records_html, metric, column, value, attribute):
    html = records_html.replace("3BVS", column).replace("6.122", value)
    if metric == RecordMetric.DENSITY:
        html = html.replace("Beginner", "9x9")
    record = parse_records(html, 42, metric)[0]
    assert getattr(record, attribute) == Decimal(value)
    if metric == RecordMetric.DENSITY:
        assert record.groups[0] == "9x9"


@pytest.mark.parametrize("value", ["nan", "Infinity", "abc"])
def test_invalid_numbers_fail(records_html, value):
    with pytest.raises(ParseError):
        parse_records(records_html.replace("0.490</a>", value + "</a>"), 42)


@pytest.mark.parametrize(
    "onclick",
    [
        "parseVideo('42','../x.avf')",
        "parseVideo('42','x.avf'); evil()",
        "parseVideo('42','x.exe')",
        "parseVideo(user, file)",
    ],
)
def test_unrecognized_or_unsafe_javascript_fails(records_html, onclick):
    html = records_html.replace("parseVideo('42','42-Time-88-NF-0,490-3.avf')", onclick)
    with pytest.raises(ParseError):
        parse_records(html, 42)


def test_missing_replay_and_empty_records(records_html):
    html = records_html.replace("onclick=\"parseVideo('42','42-Time-88-NF-0,490-3.avf')\"", "")
    assert parse_records(html, 42)[0].replay is None
    assert parse_records(records_html.replace(RECORD_ROW, ""), 42) == ()
    with pytest.raises(ParseError):
        parse_records("<html>Error page</html>", 42)
    with pytest.raises(ParseError):
        parse_records(records_html.replace("<td>3</td>", ""), 42)


def test_ranking_malformed_rows_and_scores(ranking_html):
    page = parse_ranking(ranking_html, "world", "https://minesweepergame.com/", 1)
    entry = page.entries[0]
    assert entry.player_id == 42
    assert entry.name == "测试玩家"
    assert entry.country == "china"
    assert entry.total == Decimal("50.54")
    assert [score.label for score in entry.scores] == ["Beginner", "Intermediate", "Expert"]
    assert entry.scores[0].replay.player_id == 42
    assert entry.scores[1].replay is None
    assert page.next_start is None


def test_single_density_ranking():
    html = """<table><tr><td></td><td></td><td></td><td></td><td></td><td></td>
    <td></td><td></td></tr><tr><td>1</td><td><img src=image/flags/china.gif></td>
    <td>Test Player</td><td></td><td><a onclick="parseVideo('42','test.avf')">5.99</a></td>
    <td></td><td>5.99</td><td>2024-01-02</td><tr><tr><td colspan=8></td></table>"""
    entry = parse_ranking(html, "density", "https://minesweepergame.com/", 1).entries[0]
    assert entry.player_id == 42
    assert entry.scores[0].label == "8x8"
    assert entry.scores[0].date == date(2024, 1, 2)
    assert entry.total == Decimal("5.99")


def test_ranking_layout_changes_fail(ranking_html):
    with pytest.raises(ParseError):
        parse_ranking(
            ranking_html.replace("<td>40.05</td>", ""), "world", "https://minesweepergame.com/"
        )
    with pytest.raises(ParseError):
        parse_ranking("Error page", "world", "https://minesweepergame.com/")


def test_options_ignore_placeholders():
    assert [o.value for o in parse_options(OPTIONS)] == [36, 138]
    with pytest.raises(ParseError):
        parse_options("Error page")


def test_world_record_partial_dates_rejections_and_links():
    records = parse_world_records(WORLD_RECORDS)
    assert records[0].replay.url == "https://minesweepergame.com/record/test.avf"
    assert records[0].country == "china"
    rejected = records[1]
    assert rejected.no_flags and rejected.rejected
    assert rejected.date is None
    assert rejected.date_text == "1997-00-00"
    assert rejected.value == Decimal("50.45")
    assert rejected.comment == ""
    with pytest.raises(ParseError):
        parse_world_records("Error page")
