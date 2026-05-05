#!/usr/bin/env python3
"""
Lightweight benchmarking harness for Sauron's Eye.

Features:
- Run existing backend profiler tests (uses `backend_performance_profiler.BackendPerformanceProfiler`).
- Run a simple frontend timing test that measures how long a `/viewer/load_psg` response takes
  after clicking the "Next" button in the viewer using Playwright.

Usage examples:
  python3 bench/benchmark_timings.py --backend
  python3 bench/benchmark_timings.py --frontend --app-url http://localhost:5000

Notes:
- Frontend tests require the webapp to be running and a logged-in test user. Playwright
  needs browser binaries (see README) and may require `playwright install`.
"""

import argparse
import time
import sys
import os

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def run_backend_profile():
    """Run the repository's backend profiler and print summary."""
    try:
        from backend_performance_profiler import BackendPerformanceProfiler
    except Exception as e:
        print(f"Could not import backend profiler: {e}")
        return

    profiler = BackendPerformanceProfiler()
    profiler.run_comprehensive_profile()


def run_frontend_next_timing(app_url: str, repetitions: int = 5, headless: bool = True):
    """Measure time between clicking 'Next' and receiving the `/viewer/load_psg` response.

    This uses Playwright to load the viewer page, waits until the viewer has an accessible
    Next button (input image with title="Next"), then clicks it `repetitions` times and
    records the durations.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        print("Playwright not installed. Install with: pip install playwright")
        return

    selector = 'input[title="Next"]'

    durations = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        print(f"Navigating to {app_url}")
        page.goto(app_url)

        # Wait for page to expose the Next button
        try:
            page.wait_for_selector(selector, timeout=15000)
        except Exception as e:
            print(f"Next button not found within timeout: {e}")
            browser.close()
            return

        # Helper to capture response time of /viewer/load_psg
        for i in range(repetitions):
            # Clear any previous timestamps
            timestamps = []

            def _on_response(resp):
                try:
                    if '/viewer/load_psg' in resp.url and resp.request.method == 'POST':
                        timestamps.append(time.perf_counter())
                except Exception:
                    pass

            page.on('response', _on_response)

            start = time.perf_counter()
            page.click(selector)

            # Wait up to 10s for the response handler to record a timestamp
            waited = 0.0
            while waited < 10.0 and len(timestamps) == 0:
                time.sleep(0.05)
                waited += 0.05

            if len(timestamps) == 0:
                print(f"Iteration {i+1}: no /viewer/load_psg response captured")
                durations.append(None)
            else:
                dur = timestamps[0] - start
                durations.append(dur)
                print(f"Iteration {i+1}: {dur:.4f}s")

            # Remove handler to avoid accumulating listeners
            try:
                page.off('response', _on_response)
            except Exception:
                pass

        browser.close()

    # Summary
    valid = [d for d in durations if d is not None]
    print("\nFrontend Next-click timing results:")
    print(f"  Runs: {len(durations)}  Successful: {len(valid)}")
    if valid:
        print(f"  Avg: {sum(valid)/len(valid):.4f}s  Min: {min(valid):.4f}s  Max: {max(valid):.4f}s")
    else:
        print("  No successful measurements captured")


def main():
    parser = argparse.ArgumentParser(description="Sauron's Eye timing benchmarks")
    parser.add_argument('--backend', action='store_true', help='Run backend profiler')
    parser.add_argument('--frontend', action='store_true', help='Run frontend Next-button timing (Playwright)')
    parser.add_argument('--app-url', type=str, default='http://localhost:5000', help='App URL for frontend tests')
    parser.add_argument('--repetitions', type=int, default=5, help='Number of Next clicks to time')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')

    args = parser.parse_args()

    if not args.backend and not args.frontend:
        print('No tests selected. Use --backend and/or --frontend')
        return

    if args.backend:
        print('\n=== Running backend profiler ===')
        run_backend_profile()

    if args.frontend:
        print('\n=== Running frontend Next-button timing ===')
        run_frontend_next_timing(args.app_url, repetitions=args.repetitions, headless=args.headless)


if __name__ == '__main__':
    main()
