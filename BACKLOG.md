# Iocane Harness Backlog

Append-only. Do not delete entries. Use checkboxes to mark resolved items.

---

## Open

- [ ] **[DESIGN] io-orchestrate overlap with io-plan-batch** — `io-orchestrate` generates task files (Step C), scores the confidence rubric (Step D), and writes `plans/tasks/run.sh` (Step E). `io-plan-batch` now owns task file generation, confidence scoring, and human approval. `io-orchestrate` should likely be stripped to dispatch-only: remove Steps C/D, decide whether Step E (`run.sh` generation) is still needed or whether `dispatch-agents.sh` fully replaces it. Review the full chain before the next session working on this workflow.

- [ ] **[DESIGN] doc-sync sentinel cleanup** — `/doc-sync` (Step C, factual corrections to `project-spec.md`) uses the `.iocane/validating` sentinel to exempt its writes from `reset-on-project-spec-write.sh`. Unlike `/io-clarify`, `/io-architect`, and `/validate-plan`, doc-sync does not end its sentinel window with a recognized stamp write, so the hook cannot auto-delete the sentinel. Currently requires explicit agent cleanup (`bash: rm -f .iocane/validating` after all writes). Options to revisit:
  - Have doc-sync write a no-op "sync complete" touch to a known file that a hook can use as a cleanup signal.
  - Introduce a separate sentinel scope (e.g. `.iocane/validating-sync`) with its own hook rule, separate from the stamp sentinel.
  - Accept explicit agent cleanup for doc-sync and rely on session-start fallback; document the risk clearly.
  - Restructure doc-sync to write the stamp last (read current stamp, re-write it after corrections) so the hook can auto-detect completion — but this creates a false stamp write which may have other unintended side effects.
