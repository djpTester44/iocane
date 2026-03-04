# Execution Progress Log

Append-only ledger of completed tasks from the io-loop state machine. This file is updated statelessly via `.agent/scripts/log_progress.sh` and must strictly remain outside the LLM context window during the `io-loop` execution to prevent token degradation.

| Timestamp (UTC) | Task ID | Status | Notes |
| :--- | :--- | :--- | :--- |