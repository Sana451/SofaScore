from __future__ import annotations

import argparse
import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable

import httpx

from .config import Settings
from .main import create_app

LIVE_ENDPOINT = "/api/v1/sport/football/events/live"


@dataclass(frozen=True)
class BenchmarkResult:
    iterations: int
    warmup: int
    p50_ms: float
    p95_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    status_code: int


def percentile(samples: list[float], percentile_value: float) -> float:
    if not samples:
        raise ValueError("samples must not be empty")
    values = sorted(samples)
    if len(values) == 1:
        return values[0]
    index = (len(values) - 1) * percentile_value
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    fraction = index - lower
    return values[lower] + (values[upper] - values[lower]) * fraction


async def _measure_endpoint_async(iterations: int, warmup: int, app) -> tuple[list[float], int]:
    samples: list[float] = []
    status_code = 0
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        for _ in range(warmup):
            response = await client.get(LIVE_ENDPOINT)
            status_code = response.status_code

        for _ in range(iterations):
            start = time.perf_counter_ns()
            response = await client.get(LIVE_ENDPOINT)
            elapsed_ms = (time.perf_counter_ns() - start) / 1_000_000
            samples.append(elapsed_ms)
            status_code = response.status_code
            if response.status_code != 200:
                raise RuntimeError(f"unexpected status code: {response.status_code}")

    return samples, status_code


def measure_endpoint(
    iterations: int, warmup: int, settings: Settings | None = None
) -> BenchmarkResult:
    app = create_app(settings)
    samples, status_code = asyncio.run(_measure_endpoint_async(iterations, warmup, app))

    return BenchmarkResult(
        iterations=iterations,
        warmup=warmup,
        p50_ms=percentile(samples, 0.50),
        p95_ms=percentile(samples, 0.95),
        avg_ms=mean(samples),
        min_ms=min(samples),
        max_ms=max(samples),
        status_code=status_code,
    )


def format_result(result: BenchmarkResult) -> str:
    return "\n".join(
        [
            "Mini SofaScore live endpoint benchmark",
            f"iterations: {result.iterations}",
            f"warmup: {result.warmup}",
            f"status_code: {result.status_code}",
            f"p50_ms: {result.p50_ms:.3f}",
            f"p95_ms: {result.p95_ms:.3f}",
            f"avg_ms: {result.avg_ms:.3f}",
            f"min_ms: {result.min_ms:.3f}",
            f"max_ms: {result.max_ms:.3f}",
        ]
    )


def save_result(result: BenchmarkResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_result(result) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark the live football endpoint")
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = measure_endpoint(args.iterations, args.warmup)
    report = format_result(result)
    print(report)
    if args.output is not None:
        save_result(result, args.output)
        print(f"\nSaved benchmark report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
