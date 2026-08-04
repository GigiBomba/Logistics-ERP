# Performance Measurement Scripts

## Prerequisites
- `test_group1.db` test database in project root
- Python environment with all dependencies

## Quick Start

### Sequential Navigation (recommended first run)
```
python scripts/run_measurements.py --scenario sequential_nav
```
Navigates through every view, waits 3s each, reports timings.

### Rapid Switch (stress test)
```
python scripts/run_measurements.py --scenario rapid_switch
```
Switches between views rapidly every 300ms to test animation/layout.

### Leak Detection (long run)
```
python scripts/run_measurements.py --scenario stay_alive --duration 28800
```
Keeps the app running for 8 hours. Check memory usage externally.

## Report Output
Reports are saved to `reports/` directory as:
- `perf_report_YYYYMMDD_HHMMSS.json` — raw data
- `perf_report_YYYYMMDD_HHMMSS.md` — human-readable summary

## Manual Collection
From a Python console inside the running app:
```python
from scripts.perf_collector import collect_measurements, generate_report
report = collect_measurements(window, "sequential_nav")
generate_report(report)
```
