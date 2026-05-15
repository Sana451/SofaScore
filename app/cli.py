from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from .benchmark import format_result, measure_endpoint, save_result
from .config import Settings, get_settings
from .db import connect, initialize_database, seed_from_fixture


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mini SofaScore service utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init-db", help="Apply migrations and seed from fixture if empty")
    ingest_parser = subparsers.add_parser(
        "ingest-fixture", help="Ingest the fixture into the database"
    )
    ingest_parser.add_argument("--fixture", type=Path, default=None)
    benchmark_parser = subparsers.add_parser("benchmark", help="Measure live endpoint latency")
    benchmark_parser.add_argument("--iterations", type=int, default=500)
    benchmark_parser.add_argument("--warmup", type=int, default=50)
    benchmark_parser.add_argument("--output", type=Path, default=None)
    return parser


def command_init_db(settings: Settings) -> int:
    initialize_database(settings)
    print(f"Database initialized at {settings.db_path}")
    return 0


def command_ingest_fixture(settings: Settings, fixture_path: Path | None) -> int:
    initialize_database(
        Settings(db_path=settings.db_path, fixture_path=settings.fixture_path, auto_seed=False)
    )
    path = fixture_path or settings.fixture_path
    with connect(settings.db_path) as conn:
        seed_from_fixture(conn, path)
    print(f"Fixture ingested from {path}")
    return 0


def command_benchmark(settings: Settings, iterations: int, warmup: int, output: Path | None) -> int:
    result = measure_endpoint(iterations=iterations, warmup=warmup, settings=settings)
    report = format_result(result)
    print(report)
    if output is not None:
        save_result(result, output)
        print(f"\nSaved benchmark report to {output}")
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    settings = get_settings()
    if args.command == "init-db":
        return command_init_db(settings)
    if args.command == "ingest-fixture":
        return command_ingest_fixture(settings, args.fixture)
    if args.command == "benchmark":
        return command_benchmark(settings, args.iterations, args.warmup, args.output)
    parser.error(f"Unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
