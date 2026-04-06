# Project Name

One sentence pitch describing what the project does.

## Overview

Paragraph describing the problem this tool solves and the core methodology.

## Architecture

This project follows a strict Macro/Meso/Micro Hierarchy (Design > Contracts > Code).

* **Design Anchors:** See [`plans/project-spec.md`](./plans/project-spec.md) for CRC cards and Protocol definitions.
* **Roadmap & Status:** See [`plans/plan.yaml`](./plans/plan.yaml) for current progress and active checkpoints.
* **Meso-State:** See [`plans/execution-handoff-bundle.md`](./plans/execution-handoff-bundle.md) for current meso-state.

## Prerequisites

* Python 3.12+
* `uv` package manager

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Activate environment
source .venv/bin/activate

# 3. Run the main entry point
uv run python -m src.main
```

## Development

* **Linting:** `uv run rtk ruff check .`
* **Testing:** `uv run rtk pytest`
* **Type Checking:** `uv run mypy .`

## Project Structure

* `src/` - Application code
* `interfaces/` - Type stubs and Protocols (.pyi)
* `plans/` - Documentation and Agent context
  * `project-spec.md` - Technical specs
  * `progress.md` - Work log
  * `plan.yaml` - Roadmap & Status
  * `execution-handoff-bundle.md` - Meso-state
