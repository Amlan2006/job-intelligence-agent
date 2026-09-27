"""Run startup discovery once or periodically while this local worker remains running."""

import argparse
import asyncio
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.db.repositories.discovery import DiscoveryBusy
from app.main import create_app
from app.schemas.discovery import DiscoveryRequest
from app.services.discovery import ResumeNotFound


async def run(args):
    app = create_app()
    payload = DiscoveryRequest(
        resume_id=args.resume_id,
        source=args.source,
        lookback_days=args.lookback_days,
        limit=args.limit,
        categories=args.category,
    )
    async with app.router.lifespan_context(app):
        while True:
            try:
                report = await app.state.discovery_service.run(payload)
                print(report.model_dump_json(), flush=True)
                if report.status == "failed" and any(
                    warning in {"DEFILLAMA_API_KEY_REQUIRED", "TAVILY_API_KEY_REQUIRED"}
                    for warning in report.warnings
                ):
                    return 2
                if not args.watch:
                    return 1 if report.status == "failed" else 0
            except DiscoveryBusy:
                if not args.watch:
                    print("DISCOVERY_ALREADY_RUNNING", flush=True)
                    return 1
            except ResumeNotFound:
                print("RESUME_NOT_FOUND", flush=True)
                return 2
            except SQLAlchemyError:
                print("DATABASE_ERROR", flush=True)
                if not args.watch:
                    return 1
            await asyncio.sleep(args.interval_hours * 3600)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("resume_id", type=UUID)
    parser.add_argument("--source", choices=["tavily", "defillama"], default="tavily")
    parser.add_argument("--limit", type=int, choices=range(1, 11), default=3)
    parser.add_argument("--lookback-days", type=int, choices=range(1, 366), default=90)
    parser.add_argument("--category", action="append", default=[])
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval-hours", type=float, default=24)
    args = parser.parse_args()
    if not 1 <= args.interval_hours <= 8760:
        parser.error("--interval-hours must be between 1 and 8760")
    try:
        raise SystemExit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
