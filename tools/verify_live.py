"""Explicit, finite live validation. Never run as part of offline CI."""

import argparse
import asyncio
import hashlib
import json
import ssl
from datetime import UTC, datetime
from pathlib import Path

import httpx

from msgames_api import AsyncClient, Client, DensityBoard, RecordMetric


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--player-id", type=int, default=7872)
    parser.add_argument("--output", type=Path, default=Path("docs/research/live-validation.json"))
    parser.add_argument(
        "--system-ca", action="store_true", help="use optional truststore system CAs"
    )
    parser.add_argument(
        "--download", action="store_true", help="also fetch one publicly linked replay"
    )
    args = parser.parse_args()
    context = ssl.create_default_context()
    if args.system_ca:
        import truststore

        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    result = {
        "checked_at": datetime.now(UTC).isoformat(),
        "player_id": args.player_id,
        "checks": {},
    }
    checks = result["checks"]
    with httpx.Client(verify=context, timeout=30) as http:
        with Client(http_client=http) as api:
            profile = api.get_profile(args.player_id)
            assert profile.name
            checks["profile"] = {
                "fields": list(profile.fields),
                "unicode_name_present": bool(profile.local_name),
            }
            downloadable = None
            for metric in RecordMetric:
                records = api.get_records(args.player_id, metric)
                checks[f"records_{metric.name.lower()}"] = {
                    "count": len(records),
                    "replays": sum(r.replay is not None for r in records),
                }
                downloadable = downloadable or next((r.replay for r in records if r.replay), None)
            for source in ("world", "arbiter"):
                ranking = api.get_ranking(source=source)
                assert ranking.entries
                checks[f"ranking_{source}"] = {
                    "count": len(ranking.entries),
                    "next_start": ranking.next_start,
                }
            countries = api.get_countries()
            china = next(c for c in countries if c.label == "China")
            regions = api.get_country_regions(china.value)
            checks["country_options"] = {"countries": len(countries), "regions": len(regions)}
            ranking = api.get_country_ranking(china.value)
            assert ranking.entries and all(e.country == "china" for e in ranking.entries)
            checks["ranking_country"] = {"count": len(ranking.entries)}
            ranking = api.get_density_ranking()
            checks["ranking_density"] = {"count": len(ranking.entries)}
            options = api.get_density_options(DensityBoard.EIGHT_BY_EIGHT)
            ranking = api.get_density_ranking(DensityBoard.EIGHT_BY_EIGHT, mines=options[-1].value)
            checks["ranking_density_board"] = {
                "count": len(ranking.entries),
                "mines": options[-1].value,
            }
            world_records = api.get_world_records()
            checks["world_records"] = {
                "count": len(world_records),
                "rejected": sum(r.rejected for r in world_records),
            }
            if args.download and downloadable:
                data = api.download_replay(downloadable)
                checks["replay_download"] = {
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }

    async def check_async() -> None:
        async with httpx.AsyncClient(verify=context, timeout=30) as http:
            async with AsyncClient(http_client=http) as api:
                profile = await api.get_profile(args.player_id)
                records = await api.get_records(args.player_id)
                assert profile.name and records
                checks["async_profile_and_records"] = {"records": len(records)}

    asyncio.run(check_async())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
