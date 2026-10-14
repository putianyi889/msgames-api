"""Small JSON command-line interface; downloads never overwrite existing files."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .client import Client
from .exceptions import MsgamesError
from .models import RecordMetric


def main() -> int:
    parser = argparse.ArgumentParser(description="Read public MinesweeperGame.com data")
    sub = parser.add_subparsers(dest="command", required=True)
    profile = sub.add_parser("profile")
    profile.add_argument("player_id", type=int)
    records = sub.add_parser("records")
    records.add_argument("player_id", type=int)
    records.add_argument("--metric", choices=[m.name.lower() for m in RecordMetric], default="time")
    ranking = sub.add_parser("ranking")
    ranking.add_argument("--source", choices=["world", "arbiter"], default="world")
    ranking.add_argument("--metric", type=int, choices=range(1, 6), default=1)
    ranking.add_argument("--start", type=int, default=0)
    sub.add_parser("world-records")
    download = sub.add_parser("download")
    download.add_argument("url")
    download.add_argument("output", type=Path)
    args = parser.parse_args()
    data: dict[str, Any] | list[dict[str, Any]]
    try:
        with Client() as client:
            if args.command == "profile":
                data = client.get_profile(args.player_id).to_dict()
            elif args.command == "records":
                metric = RecordMetric[args.metric.upper()]
                data = [r.to_dict() for r in client.get_records(args.player_id, metric)]
            elif args.command == "ranking":
                data = client.get_ranking(
                    args.metric, source=args.source, start=args.start
                ).to_dict()
            elif args.command == "world-records":
                data = [r.to_dict() for r in client.get_world_records()]
            else:
                if args.output.exists():
                    raise FileExistsError(args.output)
                content = client.download_replay(args.url)
                with args.output.open("xb") as file:
                    file.write(content)
                print(str(args.output))
                return 0
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    except (MsgamesError, ValueError, OSError) as exc:
        print(f"msgames-api: {exc}", file=sys.stderr)
        return 1
