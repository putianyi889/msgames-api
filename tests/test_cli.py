import json
import sys
from pathlib import Path

import httpx
import pytest

from msgames_api import Client, cli

from .test_clients import REPLAY_URL, handler


@pytest.mark.parametrize(
    "arguments",
    [
        ["profile", "42"],
        ["records", "42"],
        ["records", "42", "--metric", "ioe"],
        ["ranking", "--source", "arbiter"],
        ["world-records"],
    ],
)
def test_json_commands(monkeypatch, capsys, arguments):
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        monkeypatch.setattr(cli, "Client", lambda: Client(http_client=http, min_interval=0))
        monkeypatch.setattr(sys, "argv", ["msgames-api", *arguments])
        assert cli.main() == 0
    assert json.loads(capsys.readouterr().out)


def test_download_refuses_overwrite(monkeypatch, capsys, tmp_path):
    destination = tmp_path / "replay.avf"
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        monkeypatch.setattr(cli, "Client", lambda: Client(http_client=http, min_interval=0))
        monkeypatch.setattr(sys, "argv", ["msgames-api", "download", REPLAY_URL, str(destination)])
        assert cli.main() == 0
        before = destination.read_bytes()
        assert before == b"\x34\x0f\x01binary replay"
        assert cli.main() == 1
        assert destination.read_bytes() == before
    assert str(destination) in capsys.readouterr().out


def test_cli_failure_has_nonzero_exit(monkeypatch, capsys):
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429))) as http:
        monkeypatch.setattr(cli, "Client", lambda: Client(http_client=http, min_interval=0))
        monkeypatch.setattr(sys, "argv", ["msgames-api", "profile", "42"])
        assert cli.main() == 1
    captured = capsys.readouterr()
    assert "HTTP 429" in captured.err
    assert not captured.out


def test_release_metadata_and_type_marker():
    import tomllib
    from importlib.metadata import version

    import msgames_api

    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["version"] == version("msgames-api") == msgames_api.__version__
    assert Path(msgames_api.__file__).with_name("py.typed").is_file()
