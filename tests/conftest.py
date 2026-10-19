"""Synthetic fixtures retaining the public site's observed HTML structures."""

import pytest

PROFILE = """<div class="msgame-content">
<div id="picture">Log in to see Pictures.</div>
<div id="profile"><table>
<tr><td>Name</td><td>Test Player</td></tr>
<tr><td>Local Name</td><td>测试玩家</td></tr>
<tr><td>Nickname</td><td>A &amp; B</td></tr>
<tr><td>Country</td><td>China</td></tr>
<tr><td>Joined</td><td>2020-02-29</td></tr>
<tr><td>Mouse</td><td></td></tr>
<tr><td>New Field</td><td>preserved</td></tr></table></div>
<div id="sites"><table><tr><td>Website</td>
<td><a href="https://example.org/player?id=42&amp;lang=en">Example</a></td></tr></table></div>
<div id="world"><table><tr><td>Time</td><td>0</td><td>/</td><td>500</td></tr></table></div>
<div id="country"><table><tr><td>Time</td><td>2</td><td>/</td><td>10</td></tr></table>
</div></div>"""

RECORD_HEADER = """<tr><td>Date</td><td>Style</td><td>Time</td><td>3BV</td>
<td>3BVS</td><td>Program</td><td>Version</td><td>Category</td><td>Comment</td></tr>"""
RECORD_ROW = """<tr '><td>2024-01-02</td><td>NF</td>
<td><a href="javascript:void(0);" onclick="parseVideo('42','42-Time-88-NF-0,490-3.avf')">
0.490</a></td><td>3</td><td>6.122</td><td>Arbiter</td><td>0.52.3</td>
<td>Official</td><td>Test &amp; comment</td></tr>"""
RECORDS = f"""<div class="msgame-content"><ul class="nav-tabs">
<li><a href="#tab_b">Beginner</a></li><li><a href="#tab_b_nf">(NF)</a></li></ul>
<div class="tab-pane" id="tab_b"><table>{RECORD_HEADER}{RECORD_ROW}</table></div>
<div class="tab-pane" id="tab_b_nf"><table>{RECORD_HEADER}{RECORD_ROW}</table></div></div>"""

# Reduced structure observed on player 7714's public Problems page.
EMPTY_RECORDS = """<html><head><title>Player Profile</title></head><body>
<div class="container-fluid msgame-content">
<div class="row justify-content-center"><div class="col-sm-10">
<!-- No scores: the site omits tables and difficulty tabs. -->
</div></div><script>function playVideo(filePath) {}</script>
</div></body></html>"""

RANKING_HEADER = """<tr><td></td><td></td><td></td><td></td><td colspan=2>Beginner</td>
<td colspan=2>Intermediate</td><td colspan=2>Expert</td><td>TOTAL</td></tr>"""
RANKING_ROW = """<tr><td>1</td><td><img src="image/flags/china.gif">
<a href="https://minesweepergame.com/profile.php?pid=42"><img src="image/profile.png"></a>
</td><td>测试玩家</td><td></td><td><a onclick="parseVideo('42','42-Time-88-NF-0,490-3.avf')">
0.49</a></td><td>2024-01-02</td><td>10.00</td><td>2024-02-03</td><td>40.05</td>
<td>2024-03-04</td><td>50.54</td><tr>"""
RANKING = f"<table>{RANKING_HEADER}{RANKING_ROW}<tr><td colspan=11></td></table>"
OPTIONS = (
    "<option value=0>*Choose*</option><option value=36>China</option>"
    "<option value=138>Shanghai</option>"
)
WORLD_RECORDS = """<div class="msgame-content"><h5>Expert Time World Records</h5><table>
<tr><td>2024-01-02</td><td><a href="record/test.avf">26.590</a></td>
<td><img src="image/flags/china.gif"></td><td>Test Player</td><td>3BV 138</td><td></td></tr>
</table><h5>REJECTED Intermediate NF Time World Records</h5><table><tr><td>1997-00-00</td>
<td>50,45</td><td></td><td>Another Player</td><td>No evidence</td></tr></table></div>"""


@pytest.fixture
def profile_html():
    return PROFILE


@pytest.fixture
def records_html():
    return RECORDS


@pytest.fixture
def ranking_html():
    return RANKING
