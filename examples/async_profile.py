import asyncio

from msgames_api import AsyncClient, RecordMetric


async def main() -> None:
    async with AsyncClient() as api:
        profile = await api.get_profile(7872)
        records = await api.get_records(7872, RecordMetric.TIME)
        print(profile.to_dict())
        for record in records:
            if record.replay:
                print(record.time, record.replay.url)


if __name__ == "__main__":
    asyncio.run(main())
