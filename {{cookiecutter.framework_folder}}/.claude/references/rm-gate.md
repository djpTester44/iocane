# rm-gate: Allowlist-Based File Deletion Control

PreToolUse hook on Bash that blocks `rm` commands unless they match a
pattern in `.iocane/rm-allowlist.txt`.

---

## Why This Exists

Claude Code's permission system evaluates `deny > ask > allow` -- first
match wins. A broad `Bash(rm *)` deny rule blocks all `rm` commands before
any allow rule is consulted, with no way to carve exceptions. This hook
replaces that broad deny with deterministic allowlist logic: if the command
matches a pattern in the allowlist, it passes; otherwise exit 2 blocks it.

---

## Files

| File | Purpose |
|---|---|
| `.claude/hooks/rm-gate.sh` | Hook script. Extracts the command from tool input JSON, strips quoted strings and splits on shell metacharacters to detect `rm` as an executed shell command (not a substring inside quotes), then matches against allowlist patterns. Also catches `find -exec rm`. |
| `.iocane/rm-allowlist.txt` | Glob patterns, one per line. Lines starting with `#` are comments. Blank lines ignored. |
| `.claude/settings.json` | Hook registration under `hooks.PreToolUse` with `"matcher": "Bash"`. |

---

## How It Interacts With the Permission System

```
Agent calls Bash("rm -f .iocane/validating")
  |
  v
Permission system evaluates deny list
  - Bash(rm -rf *) -- no match (not recursive)
  - Bash(rmdir *)  -- no match (not rmdir)
  - (Bash(rm *) was removed -- hook handles this now)
  |
  v
PreToolUse hooks fire
  - rm-gate.sh checks allowlist
    - Match found -> exit 0 -> tool executes
    - No match    -> exit 2 -> BLOCKED
```

The deny list retains `Bash(rm -rf *)` and `Bash(rmdir *)` as
defense-in-depth. These fire before the hook and hard-block recursive
deletes regardless of the allowlist.

---

## Allowlist Format

Each line is a bash glob pattern matched against the full command string
using `[[ $COMMAND == $pattern ]]`.

```
# .iocane/rm-allowlist.txt

# Allow iocane validation cleanup
rm -f */.iocane/validating

# Allow removing build artifacts (example)
rm -f build/*.tmp
```

Patterns use standard bash glob syntax: `*` matches any string, `?` matches
one character, `[abc]` matches character classes.

---

## Adding a New Exception

1. Open `.iocane/rm-allowlist.txt`
2. Add a glob pattern matching the command you want to allow
3. No restart or settings change needed -- the hook reads the file on every invocation

---

## Troubleshooting

**Hook blocks a command that should be allowed:**
Check that the pattern in `rm-allowlist.txt` matches the *exact* command
string. The match is `[[ $COMMAND == $pattern ]]` -- the pattern must cover
the full command, not a substring.

**Command blocked by permission system before hook fires:**
The deny list still contains `Bash(rm -rf *)` and `Bash(rmdir *)`. These
fire before any hook. If you need to allow a specific `rm -rf` command,
you would need to narrow that deny rule too -- but think carefully before
doing so.

**Hook not firing at all:**
Verify the hook entry exists in `.claude/settings.json` under
`hooks.PreToolUse` with `"matcher": "Bash"` and that the command path
resolves correctly from the project root.

---

## Settings.json Integration

The hook must be registered in the target repo's `.claude/settings.json`.
Add this entry to the `hooks.PreToolUse` array alongside the existing
Bash-matched hooks:

```json
{
  "matcher": "Bash",
  "hooks": [
    {
      "type": "command",
      "command": "bash .claude/hooks/rm-gate.sh"
    }
  ]
}
```

The corresponding `permissions.deny` list should include `Bash(rm -rf *)`
and `Bash(rmdir *)` but NOT `Bash(rm *)` -- that broad rule is what the
hook replaces.
