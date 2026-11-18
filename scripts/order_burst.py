"""Black Friday simulator: send many orders to orders-api at the same time.

Only uses the Python standard library: no virtual environment needed.

    python3 scripts/order_burst.py --url "$ORDERS_API_URL" --count 200 --workers 20
"""
import argparse
import json
import random
import subprocess
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def identity_token():
    """orders-api does not allow anonymous calls: get an ID token from gcloud."""
    return subprocess.run(['gcloud', 'auth', 'print-identity-token'], check=True,
                          capture_output=True, text=True).stdout.strip()


def send_order(url, token):
    body = json.dumps({'customer_id': random.randint(1, 10),
                       'total_price': round(random.uniform(5, 500), 2)}).encode()
    request = urllib.request.Request(f'{url}/orders', data=body, method='POST', headers={
        'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, time.perf_counter() - started
    except urllib.error.HTTPError as err:
        return err.code, time.perf_counter() - started
    except urllib.error.URLError:
        return 0, time.perf_counter() - started


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--url', required=True, help='orders-api URL (https://...run.app)')
    parser.add_argument('--count', type=int, default=200, help='number of orders to send')
    parser.add_argument('--workers', type=int, default=20, help='orders sent in parallel')
    args = parser.parse_args()

    token = identity_token()
    url = args.url.rstrip('/')
    print(f'Sending {args.count} orders to {url} with {args.workers} parallel workers...')
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda _: send_order(url, token), range(args.count)))
    elapsed = time.perf_counter() - started

    ok = sum(1 for status, _ in results if status == 201)
    latencies = sorted(latency for _, latency in results)
    print(f'Done in {elapsed:.1f}s: {ok} accepted, {len(results) - ok} failed')
    print(f'Latency  median {latencies[len(latencies) // 2] * 1000:.0f} ms · '
          f'p95 {latencies[int(len(latencies) * 0.95) - 1] * 1000:.0f} ms · '
          f'max {latencies[-1] * 1000:.0f} ms')
    failures = sorted({status for status, _ in results if status != 201})
    if failures:
        print(f'Failed status codes: {failures} (0 = connection error)')


if __name__ == '__main__':
    main()
