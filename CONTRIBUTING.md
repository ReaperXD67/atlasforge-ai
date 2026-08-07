# Contributing to AtlasForge AI

1. Create a branch from `main`.
2. Use Python 3.11 or 3.12.
3. Install `pip install -e ".[dev]"`.
4. Run `ruff check src tests` and `pytest`.
5. Never commit generated media, model weights, API keys, OAuth files, or user research data.
6. New paid providers must declare a conservative cost estimate and remain behind the daily budget scheduler.
7. New media sources must save provenance/license metadata.
8. Policy gates may become stricter; do not weaken them without an explicit documented rationale and tests.
