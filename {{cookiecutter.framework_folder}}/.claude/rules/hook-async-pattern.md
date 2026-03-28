# Hook Async Pattern: Advisory Hooks Should Not Block

> Synchronous hooks that cannot influence an operation's outcome still block it. The cost is wall-time on every Edit/Write call with no gate benefit.

## Cost Model

A synchronous advisory hook on Edit/Write fires and completes before Claude's next action. If the hook takes 200ms and the session has 100 file writes, that adds 20 seconds of wall-time. When the hook cannot block, approve, or redirect the operation, every millisecond is overhead.

Setting `"async": true` on a hook runs it in the background. Claude proceeds immediately while the hook executes concurrently. Use this for any hook whose job is to log, validate post-facto, sync state, or generate context -- not to gate.

## [HARD] Constraint

Async hooks cannot use decision control fields. If a hook needs to block (`decision: block`), approve (`permissionDecision`), or force continuation (`continue`), it must remain synchronous. Async is only safe for hooks with no control path.

Current harness hooks that qualify for async promotion:
- `backlog-tag-validate.sh` -- PostToolUse Edit/Write, validates tags, no block path
- `archive-sync.sh` -- PostToolUse Edit/Write, syncs archive, no block path
- `py-create-context.sh` -- PreToolUse Edit/Write, generates context hint, no block path

When authoring a new hook, default to async if the hook logs, notifies, or syncs -- and has no branch that outputs a decision control field.
