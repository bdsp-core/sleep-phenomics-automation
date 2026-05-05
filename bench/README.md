# Benchmarks

This folder contains a small benchmarking harness for Sauron's Eye.

Files
- `benchmark_timings.py`: CLI to run backend and frontend timing checks.

Frontend (Playwright) requirements
- Install Playwright and browser binaries:

```bash
pip install -r requirements.txt
playwright install
```

Running
- Backend profiler (no Flask server required):

```bash
python3 bench/benchmark_timings.py --backend
```

- Frontend Next-button timing (requires app running and a logged-in test user):

```bash
python3 bench/benchmark_timings.py --frontend --app-url http://localhost:5000 --repetitions 5
```

Notes
- The frontend test measures the time between clicking the viewer "Next" control and the
  `/viewer/load_psg` response. The app must already have an active session and a selected
  PSG file for the viewer to work.
