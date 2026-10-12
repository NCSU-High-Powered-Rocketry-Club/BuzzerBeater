# Payload Data Processing Template

A template for Python-based payload projects. Our [AirbrakesV2](https://github.com/NCSU-High-Powered-Rocketry-Club/AirbrakesV2) project as well as our [Payload-2025-2026](https://github.com/NCSU-High-Powered-Rocketry-Club/Payload-2025-2026) and [Payload-2024-2025](https://github.com/NCSU-High-Powered-Rocketry-Club/Payload-2024-2025) projects used this design.

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for fast Python package management.

1. Clone the repository.
2. Sync the dependencies:
   ```bash
   uv sync
   ```

## Usage

### 1. Real Flight Mode
How to run the code on the flight computer.
```bash
uv run real
```

### 2. Mock Replay Mode
Replays log flight data. 
```bash
uv run mock path/to/data.csv
```

**Optional Flags:**
* `-f` or `--fast-replay`: Run the replay at maximum speed instead of real-time.
* `-l` or `--keep-log-file`: Keep the log file after the replay stops.

### 3. Pretend Replay Mode
Replays log flight data specifically from `.frm` files. You need to have a FIRM connected to do this.
```bash
uv run pretend path/to/data.frm
```

## Project Structure

* **`payload/main.py`**: The application entry points (`run_real_flight`, `run_mock_flight`, `run_pretend_flight`).
* **`payload/context.py`**: The core state machine and orchestrator.
* **`payload/data_processor.py`**: High-level numerical processing (altitude zeroing, vertical velocity integration).
* **`payload/state.py`**: The state machine states.


## BUZZER TESTS

- verify buzzer, wiring, and gpiozero: 
```bash
uv run python -c "from gpiozero import Buzzer; import time; b = Buzzer(26); b.beep(on_time=0.5, off_time=0.5, n=5, background=False)"
```

- test LandedState directly: 
```bash
uv run python -c "from unittest.mock import MagicMock; from payload.state import LandedState; s = LandedState(MagicMock(), duration_seconds=5); s._buzzer_thread.join()"
```

- end to end flight test: 
```bash
uv run mock launch_data/real_firm_launches/jackpot_launch_4.csv -f
```