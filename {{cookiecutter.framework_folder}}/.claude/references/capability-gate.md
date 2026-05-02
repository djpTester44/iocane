# CAPABILITY-GATE: Workflow Write-Authorization Primitive

> Workflow steps issue time-bounded capability grants declaring which paths
> they will write and remove. Every gate hook consults active capabilities
> to distinguish workflow-authored operations from unauthored ones. Grants
> expire; explicit revoke is primary; TTL is the crash-safety floor.

## Cost Model

Pre-refactor, a five-mechanism tangle (sentinel file, inline cross-hook
`rm -f`, TTL helper, allowlist hook, user-global gate) compensated for one
missing primitive: workflow-authored write authorization. Each mechanism
had a narrow purpose; together they produced cross-hook coupling,
user-maintained global state, and an escape-hatch pattern
(`python -c "os.remove(...)"`) that eroded the very protection the gate
was meant to provide.

The capability primitive replaces all five with one authorization model:
a step declares its scope up-front, hooks consult that declaration, and
the step revokes at completion. Nothing implicit; nothing coupled across
hooks.

## [HARD] Storage Layout

All capability state lives under `$IOCANE_REPO_ROOT/.iocane/sessions/`.
Subagents write here too via the `$IOCANE_REPO_ROOT` env-var idiom
(exported by `dispatch-agents.sh` before every subagent spawn). `.iocane/`
stays gitignored; cross-worktree writes use absolute paths.

```
$IOCANE_REPO_ROOT/.iocane/sessions/
  manifest.yaml                       LRU last-50 sessions (YAML: human-read)
  .current-session-id                 main-session pointer (for subagent env-export)
  <session_id>.jsonl                  per-session grant/revoke log (JSONL: append-only)
  <session_id>.active.txt             hot-path cache (flat text: bash-grep)
  archive/YYYY-MM/
    <session_id>.jsonl                archived event log
    <session_id>.manifest-entry.json  frozen metadata snapshot (JSON: forensic)
```

**Session id source:** Claude Code's own `session_id` (top-level field in
every hook payload), used verbatim as filename basename. Cross-references
trivially with `~/.claude/projects/<hash>/<session_id>.jsonl` (the Claude
Code transcript log).

## Components

- **`.claude/scripts/capability.py`** -- sole writer for capability state.
  File-locked via atomic `O_CREAT|O_EXCL` lockfile with retry; same script
  handles grant, revoke, session-start, session-end, sweep-orphans,
  list-active, migrate-legacy. Reads no env vars (entrypoint hygiene);
  callers pass `--repo-root`, `--cp-id`, `--parent-session-id`, `--subagent`
  explicitly.
- **`.claude/hooks/capability-gate.sh`** -- PreToolUse hot-path hook.
  Bash-only. Hardcoded catastrophic-rm deny list (minimal, evidence-added
  only). Fails OPEN otherwise. Does not consult the capability cache in
  Phase 1: cache consumers are the reset-on-\*.sh hooks, not this gate.
- **`.claude/capability-templates/<workflow>.<step>.yaml`** -- static grant
  templates. Agents never author grant payloads at runtime; they invoke
  by template name only (`capability.py grant --template io-architect.H`).
  Templates are git-tracked, PR-reviewable, serve as the authoritative
  catalog of what each workflow step writes.

## Grant Lifecycle

1. **Step pre-work:** `capability.py grant --template <name>` writes a
   `type:grant` record to the session JSONL and atomically rewrites the
   hot-path `active.txt` cache.
2. **During work:** the workflow writes its declared paths. Reset/gate
   hooks consult `active.txt` (Phase 2+) to recognize these as authorized
   and suppress their reset behavior.
3. **Step post-work:** `capability.py revoke --template <name>` writes a
   matching `type:revoke` record. Cache is rewritten.
4. **Session end:** any still-active grants are revoked; JSONL + manifest
   entry move to `archive/YYYY-MM/`.

Workflows that iterate at the impl tier (e.g., io-architect's bounded
A5/A6 wire-test critic retries per Plan B Phase 5) re-issue the grant
at each cycle entry. Each re-grant produces a fresh `entry_id`; a single
`revoke --template` at workflow end clears all accumulated grants matching
the template name. Cycle re-entry can be deterministic (a PostToolUse
hook re-grants on the workflow's known boundary tool call, e.g.,
`regrant-on-evaluator-return.sh` fires on architect's return from
`spawn-artifact-evaluator.sh` -- but only on `--rubric cdt`/`--rubric ct`
paths; the `--rubric design` path is single-pass per architect attempt
under R2-narrow + D-04 clause-5 option a, with no auto-regrant) or
prose-driven (the agent re-invokes the grant command at the cycle-entry
step).

A grant is **live** iff:

- a `type:grant` record with entry_id X exists,
- no `type:revoke` record with entry_id X follows,
- `now < granted_at + min(declared_ttl, 86400)` (24h hard ceiling clamps
  buggy template authors).

## [HARD] Parallel Fan-out Pattern

Workflows that fan out parallel per-target subprocesses (currently
`/io-wire-tests-cdt` and `/io-wire-tests-ct` via `xargs -P`) must NOT
rely on the `.current-session-id` fallback for their grant ledger.
Under fan-out, that file is shared mutable state -- any subprocess that
triggers a `capability.py session-start` without `--subagent` will
overwrite it, which corrupts every other subprocess's grant resolution
mid-run.

The discipline has three parts; all are required:

1. **Orchestrator brackets its own run.** Mint a per-run `SESSION_ID`,
   capture the parent SID from `.current-session-id` BEFORE any
   subprocess work, then call `capability.py session-start
   --session-id "$SESSION_ID" --subagent --parent-session-id
   "$PARENT_SID" --source "<workflow>"` before fan-out and
   `session-end --session-id "$SESSION_ID"` after the post-batch
   barrier. Both calls fail-open (`|| true`); `sweep-orphans` cleans
   stragglers within 24h.

2. **Per-target grants thread `--session-id` explicitly.** Inside the
   per-target subprocess, every `capability.py grant` and `revoke`
   call passes `--session-id "$SESSION_ID"` (the orchestrator's
   per-run SID, exported into the subprocess env). This pins the
   grant to the orchestrator's session regardless of what other
   writers touch `.current-session-id`. Grants additionally pass
   `--subagent --parent-session-id "$PARENT_SID"` for audit
   correctness (metadata only; does not affect file mutation).

3. **Spawned `claude -p` subprocesses export `IOCANE_SUBAGENT=1`.** Any
   spawn script that invokes `claude -p` to run a sub-agent (e.g.,
   `spawn-test-author.sh`, `spawn-test-critic.sh`) must export
   `IOCANE_SUBAGENT=1` alongside `IOCANE_PARENT_SESSION_ID`. The
   sub-agent's `session-start.sh` hook reads this env var and passes
   `--subagent` to `capability.py session-start`, which by
   `cmd_session_start` skips the `.current-session-id` overwrite
   (the file is reserved for the main interactive session pointer).

Omitting any one of these three steps re-introduces the race: per-target
grants fall back to a `.current-session-id` that sibling subprocesses
are concurrently rewriting or unlinking, causing
`resolve_session_id` to throw `RuntimeError: no session id` mid-fan-out.

## Authority vs Audit

The **hot-path cache** (`active.txt`) is the authority -- hooks read only
this file. The **JSONL log** is the audit trail -- chronological append of
grant/revoke events for forensic reconstruction.

If an agent forges a grant by appending directly to the JSONL (bypassing
`capability.py`), the cache is unchanged and the hook never sees the
forged grant. `capability.py`'s atomic cache rewrite is the chokepoint;
the log alone cannot authorize.

## Template Schema

```yaml
# .claude/capability-templates/io-architect.H.yaml
workflow: io-architect
step: H
ttl_seconds: 1800                     # 30 min; optional (default 3600)
grants:
  write:
    - plans/symbols.yaml
    - plans/plan.yaml
  rm: []
keywords: [architect, canonical-yaml-write]
context: "Architect Step H: canonical YAML write sequence"
```

Path patterns are bash glob strings; reset hooks match via
`[[ $target == $pattern ]]`.

## TTL Policy

Declared per-template; 1h fallback if unset; 24h ceiling clamped at
hook read-time. TTL is tertiary: primary guard is explicit revoke at
step-post; secondary is session-boundary sweep; TTL only fires when both
fail (agent crashes mid-step without revoking).

Suggested template values:

| Template                 | ttl_seconds |
|--------------------------|-------------|
| io-clarify.7             |  600        |
| run-state-snapshot       |  600        |
| validate-plan.13         |  600        |
| io-architect.H           | 1800        |
| io-checkpoint.H          | 1800        |
| io-design-evaluator.A    | 1800        |
| auto-architect.architect | 1800        |

None approach the 24h ceiling under normal operation.

## [HARD] Default Behaviors by Hook Semantic

Split justified by each hook's failure cost:

- **`capability-gate.sh` (PreToolUse, this hook)** -- fails **OPEN** with
  hardcoded catastrophic-rm deny. Non-catastrophic rm passes. Matches
  baseline for non-rm commands. Adds explicit protection without
  depending on a user-maintained allowlist.
- **`reset-on-*.sh` (PostToolUse)** -- fails **CLOSED**: no capability
  covers this write -> treat as unauthored -> run the reset. Mirrors
  today's sentinel-absent behavior.

## What This Does Not Replace

- `.iocane/architect-mode` -- session-spanning mode flag; different
  lifecycle, different semantic. Stays on its own file and readers.
- Content-detection + workflow-state transitions inside reset hooks
  (e.g., `validated: true` in plan.yaml). Legitimate state-machine
  logic, not a sentinel workaround. The outer condition changes from
  "is sentinel present?" to "is this write covered by a capability?"
  Inner detection + state write is unchanged.

## Migration

See §5 of the capability-gate refactor plan (chunk 2.6) for consumer-repo
migration steps. `capability.py migrate-legacy` is the one-shot cleanup
helper; actual migration execution is user-owned per standing
instruction.
