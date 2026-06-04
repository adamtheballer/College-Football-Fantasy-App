import argparse
import asyncio
import statistics
import time

import httpx


async def _worker(
    *,
    client: httpx.AsyncClient,
    url: str,
    token: str,
    requests_per_worker: int,
) -> list[float]:
    latencies: list[float] = []
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    for _ in range(requests_per_worker):
        started = time.perf_counter()
        response = await client.get(url, headers=headers, timeout=20.0)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if response.status_code >= 400:
            raise RuntimeError(f"request failed: status={response.status_code} body={response.text[:200]}")
        latencies.append(elapsed_ms)
    return latencies


async def run_load_test(
    *,
    base_url: str,
    league_id: int,
    token: str,
    workers: int,
    requests_per_worker: int,
) -> None:
    url = f"{base_url.rstrip('/')}/leagues/{league_id}/draft-room/snapshot?since_seq=0"
    async with httpx.AsyncClient() as client:
        tasks = [
            _worker(
                client=client,
                url=url,
                token=token,
                requests_per_worker=requests_per_worker,
            )
            for _ in range(workers)
        ]
        all_latencies = await asyncio.gather(*tasks)

    values = [item for sublist in all_latencies for item in sublist]
    if not values:
        print("No requests executed.")
        return

    values_sorted = sorted(values)
    p50 = values_sorted[int(len(values_sorted) * 0.50)]
    p95 = values_sorted[int(len(values_sorted) * 0.95)]
    p99 = values_sorted[int(len(values_sorted) * 0.99)]
    print("Draft snapshot load test results")
    print(f"  total_requests: {len(values)}")
    print(f"  workers: {workers}")
    print(f"  requests_per_worker: {requests_per_worker}")
    print(f"  mean_ms: {statistics.mean(values):.2f}")
    print(f"  p50_ms: {p50:.2f}")
    print(f"  p95_ms: {p95:.2f}")
    print(f"  p99_ms: {p99:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple concurrent load test for draft snapshot endpoint.")
    parser.add_argument("--base-url", type=str, default="http://localhost:8000")
    parser.add_argument("--league-id", type=int, required=True)
    parser.add_argument("--token", type=str, required=True)
    parser.add_argument("--workers", type=int, default=25)
    parser.add_argument("--requests-per-worker", type=int, default=20)
    args = parser.parse_args()

    asyncio.run(
        run_load_test(
            base_url=args.base_url,
            league_id=args.league_id,
            token=args.token,
            workers=max(1, args.workers),
            requests_per_worker=max(1, args.requests_per_worker),
        )
    )


if __name__ == "__main__":
    main()
