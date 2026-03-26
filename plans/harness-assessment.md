# Harness Assessment

**Generated:** 2026-03-26 21:21
**Mode:** full
**Docs:** cli-reference.md, hooks.md, skills.md, tools-reference.md, channels-reference.md, checkpointing.md, env-vars.md
**Findings:** 368 (37 COMMAND-CANDIDATE, 109 HOOK-CANDIDATE, 3 NEEDS-REVIEW, 167 RULE-CANDIDATE, 52 SKILL-CANDIDATE)

## Findings

| # | Capability | Source | Area | Disposition | Notes |
|---|-----------|--------|------|-------------|-------|
| 1 | --add-dir | cli-reference.md:38 | cli-flags | RULE-CANDIDATE | Add additional working directories for Claude to access (validates each path exists as a directory) |
| 2 | --agent | cli-reference.md:39 | cli-flags | RULE-CANDIDATE | Specify an agent for the current session (overrides the `agent` setting) |
| 3 | --agents | cli-reference.md:40 | cli-flags | RULE-CANDIDATE | Define custom subagents dynamically via JSON. Uses the same field names as subagent [frontmatter](/en/sub-agents#supported-frontmatter-fields), plus... |
| 4 | --allow-dangerously-skip-permissions | cli-reference.md:41 | cli-flags | HOOK-CANDIDATE | Enable permission bypassing as an option without immediately activating it. Allows composing with `--permission-mode` (use... |
| 5 | --allowedTools | cli-reference.md:42 | cli-flags | HOOK-CANDIDATE | Tools that execute without prompting for permission. See [permission rule syntax](/en/settings#permission-rule-syntax) for pattern matching. To... |
| 6 | --append-system-prompt | cli-reference.md:43 | cli-flags | RULE-CANDIDATE | Append custom text to the end of the default system prompt |
| 7 | --append-system-prompt-file | cli-reference.md:44 | cli-flags | RULE-CANDIDATE | Load additional system prompt text from a file and append to the default prompt |
| 8 | --bare | cli-reference.md:45 | cli-flags | RULE-CANDIDATE | Minimal mode: skip auto-discovery of hooks, skills, plugins, MCP servers, auto memory, and CLAUDE.md so... |
| 9 | --betas | cli-reference.md:46 | cli-flags | RULE-CANDIDATE | Beta headers to include in API requests (API key users only) |
| 10 | --channels | cli-reference.md:47 | cli-flags | RULE-CANDIDATE | (Research preview) MCP servers whose [channel](/en/channels) notifications Claude should listen for in this session. Space-separated... |
| 11 | --chrome | cli-reference.md:48 | cli-flags | RULE-CANDIDATE | Enable [Chrome browser integration](/en/chrome) for web automation and testing |
| 12 | --continue | cli-reference.md:49 | cli-flags | RULE-CANDIDATE | Load the most recent conversation in the current directory |
| 13 | --dangerously-load-development-channels | cli-reference.md:50 | cli-flags | RULE-CANDIDATE | Enable [channels](/en/channels-reference#test-during-the-research-preview) that are not on the approved allowlist, for local development. Accepts `plugin:<name>@<marketplace>` and... |
| 14 | --dangerously-skip-permissions | cli-reference.md:51 | cli-flags | RULE-CANDIDATE | Skip permission prompts (use with caution). See [permission modes](/en/permission-modes#skip-all-checks-with-bypasspermissions-mode) for what this does and does... |
| 15 | --debug | cli-reference.md:52 | cli-flags | RULE-CANDIDATE | Enable debug mode with optional category filtering (for example, `"api,hooks"` or `"!statsig,!file"`) |
| 16 | --disable-slash-commands | cli-reference.md:53 | cli-flags | RULE-CANDIDATE | Disable all skills and commands for this session |
| 17 | --disallowedTools | cli-reference.md:54 | cli-flags | RULE-CANDIDATE | Tools that are removed from the model's context and cannot be used |
| 18 | --effort | cli-reference.md:55 | cli-flags | RULE-CANDIDATE | Set the [effort level](/en/model-config#adjust-effort-level) for the current session. Options: `low`, `medium`, `high`, `max` (Opus 4.6... |
| 19 | --fallback-model | cli-reference.md:56 | cli-flags | RULE-CANDIDATE | Enable automatic fallback to specified model when default model is overloaded (print mode only) |
| 20 | --fork-session | cli-reference.md:57 | cli-flags | RULE-CANDIDATE | When resuming, create a new session ID instead of reusing the original (use with `--resume`... |
| 21 | --from-pr | cli-reference.md:58 | cli-flags | RULE-CANDIDATE | Resume sessions linked to a specific GitHub PR. Accepts a PR number or URL. Sessions... |
| 22 | --ide | cli-reference.md:59 | cli-flags | RULE-CANDIDATE | Automatically connect to IDE on startup if exactly one valid IDE is available |
| 23 | --init | cli-reference.md:60 | cli-flags | RULE-CANDIDATE | Run initialization hooks and start interactive mode |
| 24 | --init-only | cli-reference.md:61 | cli-flags | RULE-CANDIDATE | Run initialization hooks and exit (no interactive session) |
| 25 | --include-partial-messages | cli-reference.md:62 | cli-flags | RULE-CANDIDATE | Include partial streaming events in output (requires `--print` and `--output-format=stream-json`) |
| 26 | --input-format | cli-reference.md:63 | cli-flags | RULE-CANDIDATE | Specify input format for print mode (options: `text`, `stream-json`) |
| 27 | --json-schema | cli-reference.md:64 | cli-flags | RULE-CANDIDATE | Get validated JSON output matching a JSON Schema after agent completes its workflow (print mode... |
| 28 | --maintenance | cli-reference.md:65 | cli-flags | RULE-CANDIDATE | Run maintenance hooks and exit |
| 29 | --max-budget-usd | cli-reference.md:66 | cli-flags | HOOK-CANDIDATE | Maximum dollar amount to spend on API calls before stopping (print mode only) |
| 30 | --max-turns | cli-reference.md:67 | cli-flags | HOOK-CANDIDATE | Limit the number of agentic turns (print mode only). Exits with an error when the... |
| 31 | --mcp-config | cli-reference.md:68 | cli-flags | RULE-CANDIDATE | Load MCP servers from JSON files or strings (space-separated) |
| 32 | --model | cli-reference.md:69 | cli-flags | RULE-CANDIDATE | Sets the model for the current session with an alias for the latest model (`sonnet`... |
| 33 | --name | cli-reference.md:70 | cli-flags | RULE-CANDIDATE | Set a display name for the session, shown in `/resume` and the terminal title. You... |
| 34 | --no-chrome | cli-reference.md:71 | cli-flags | HOOK-CANDIDATE | Disable [Chrome browser integration](/en/chrome) for this session |
| 35 | --no-session-persistence | cli-reference.md:72 | cli-flags | HOOK-CANDIDATE | Disable session persistence so sessions are not saved to disk and cannot be resumed (print... |
| 36 | --output-format | cli-reference.md:73 | cli-flags | RULE-CANDIDATE | Specify output format for print mode (options: `text`, `json`, `stream-json`) |
| 37 | --enable-auto-mode | cli-reference.md:74 | cli-flags | RULE-CANDIDATE | Unlock [auto mode](/en/permission-modes#eliminate-prompts-with-auto-mode) in the `Shift+Tab` cycle. Requires a Team plan (Enterprise and API support... |
| 38 | --permission-mode | cli-reference.md:75 | cli-flags | RULE-CANDIDATE | Begin in a specified [permission mode](/en/permission-modes) |
| 39 | --permission-prompt-tool | cli-reference.md:76 | cli-flags | RULE-CANDIDATE | Specify an MCP tool to handle permission prompts in non-interactive mode |
| 40 | --plugin-dir | cli-reference.md:77 | cli-flags | RULE-CANDIDATE | Load plugins from a directory for this session only. Each flag takes one path. Repeat... |
| 41 | --print | cli-reference.md:78 | cli-flags | RULE-CANDIDATE | Print response without interactive mode (see [Agent SDK documentation](https://platform.claude.com/docs/en/agent-sdk/overview) for programmatic usage details) |
| 42 | --remote | cli-reference.md:79 | cli-flags | RULE-CANDIDATE | Create a new [web session](/en/claude-code-on-the-web) on claude.ai with the provided task description |
| 43 | --remote-control | cli-reference.md:80 | cli-flags | RULE-CANDIDATE | Start an interactive session with [Remote Control](/en/remote-control#interactive-session) enabled so you can also control it from... |
| 44 | --resume | cli-reference.md:81 | cli-flags | RULE-CANDIDATE | Resume a specific session by ID or name, or show an interactive picker to choose... |
| 45 | --session-id | cli-reference.md:82 | cli-flags | RULE-CANDIDATE | Use a specific session ID for the conversation (must be a valid UUID) |
| 46 | --setting-sources | cli-reference.md:83 | cli-flags | RULE-CANDIDATE | Comma-separated list of setting sources to load (`user`, `project`, `local`) |
| 47 | --settings | cli-reference.md:84 | cli-flags | RULE-CANDIDATE | Path to a settings JSON file or a JSON string to load additional settings from |
| 48 | --strict-mcp-config | cli-reference.md:85 | cli-flags | RULE-CANDIDATE | Only use MCP servers from `--mcp-config`, ignoring all other MCP configurations |
| 49 | --system-prompt | cli-reference.md:86 | cli-flags | RULE-CANDIDATE | Replace the entire system prompt with custom text |
| 50 | --system-prompt-file | cli-reference.md:87 | cli-flags | RULE-CANDIDATE | Load system prompt from a file, replacing the default prompt |
| 51 | --teleport | cli-reference.md:88 | cli-flags | RULE-CANDIDATE | Resume a [web session](/en/claude-code-on-the-web) in your local terminal |
| 52 | --teammate-mode | cli-reference.md:89 | cli-flags | RULE-CANDIDATE | Set how [agent team](/en/agent-teams) teammates display: `auto` (default), `in-process`, or `tmux`. See [set up agent... |
| 53 | --tools | cli-reference.md:90 | cli-flags | RULE-CANDIDATE | Restrict which built-in tools Claude can use. Use `""` to disable all, `"default"` for all,... |
| 54 | --verbose | cli-reference.md:91 | cli-flags | RULE-CANDIDATE | Enable verbose logging, shows full turn-by-turn output |
| 55 | --version | cli-reference.md:92 | cli-flags | RULE-CANDIDATE | Output the version number |
| 56 | --worktree | cli-reference.md:93 | cli-flags | RULE-CANDIDATE | Start Claude in an isolated [git worktree](/en/common-workflows#run-parallel-claude-code-sessions-with-git-worktrees) at `<repo>/.claude/worktrees/<name>`. If no name is given, one... |
| 57 | Event | hooks.md:27 | hook-events | HOOK-CANDIDATE | When it fires |
| 58 | SessionStart | hooks.md:29 | hook-events | HOOK-CANDIDATE | When a session begins or resumes |
| 59 | UserPromptSubmit | hooks.md:30 | hook-events | HOOK-CANDIDATE | When you submit a prompt, before Claude processes it |
| 60 | PreToolUse | hooks.md:31 | hook-events | HOOK-CANDIDATE | Before a tool call executes. Can block it |
| 61 | PermissionRequest | hooks.md:32 | hook-events | HOOK-CANDIDATE | When a permission dialog appears |
| 62 | PostToolUse | hooks.md:33 | hook-events | HOOK-CANDIDATE | After a tool call succeeds |
| 63 | PostToolUseFailure | hooks.md:34 | hook-events | HOOK-CANDIDATE | After a tool call fails |
| 64 | Notification | hooks.md:35 | hook-events | HOOK-CANDIDATE | When Claude Code sends a notification |
| 65 | SubagentStart | hooks.md:36 | hook-events | HOOK-CANDIDATE | When a subagent is spawned |
| 66 | SubagentStop | hooks.md:37 | hook-events | HOOK-CANDIDATE | When a subagent finishes |
| 67 | Stop | hooks.md:38 | hook-events | HOOK-CANDIDATE | When Claude finishes responding |
| 68 | StopFailure | hooks.md:39 | hook-events | HOOK-CANDIDATE | When the turn ends due to an API error. Output and exit code are ignored |
| 69 | TeammateIdle | hooks.md:40 | hook-events | HOOK-CANDIDATE | When an [agent team](/en/agent-teams) teammate is about to go idle |
| 70 | TaskCompleted | hooks.md:41 | hook-events | HOOK-CANDIDATE | When a task is being marked as completed |
| 71 | InstructionsLoaded | hooks.md:42 | hook-events | HOOK-CANDIDATE | When a CLAUDE.md or `.claude/rules/*.md` file is loaded into context. Fires at session start and... |
| 72 | ConfigChange | hooks.md:43 | hook-events | HOOK-CANDIDATE | When a configuration file changes during a session |
| 73 | CwdChanged | hooks.md:44 | hook-events | HOOK-CANDIDATE | When the working directory changes, for example when Claude executes a `cd` command. Useful for... |
| 74 | FileChanged | hooks.md:45 | hook-events | HOOK-CANDIDATE | When a watched file changes on disk. The `matcher` field specifies which filenames to watch |
| 75 | WorktreeCreate | hooks.md:46 | hook-events | HOOK-CANDIDATE | When a worktree is being created via `--worktree` or `isolation: "worktree"`. Replaces default git behavior |
| 76 | WorktreeRemove | hooks.md:47 | hook-events | HOOK-CANDIDATE | When a worktree is being removed, either at session exit or when a subagent finishes |
| 77 | PreCompact | hooks.md:48 | hook-events | HOOK-CANDIDATE | Before context compaction |
| 78 | PostCompact | hooks.md:49 | hook-events | HOOK-CANDIDATE | After context compaction completes |
| 79 | Elicitation | hooks.md:50 | hook-events | HOOK-CANDIDATE | When an MCP server requests user input during a tool call |
| 80 | ElicitationResult | hooks.md:51 | hook-events | HOOK-CANDIDATE | After a user responds to an MCP elicitation, before the response is sent back to... |
| 81 | SessionEnd | hooks.md:52 | hook-events | HOOK-CANDIDATE | When a session terminates |
| 82 | How a hook resolves | hooks.md:54 | hook-events | HOOK-CANDIDATE | To see how these pieces fit together, consider this `PreToolUse` hook that blocks destructive shell... |
| 83 | Hook locations | hooks.md:152 | hook-events | HOOK-CANDIDATE | Where you define a hook determines its scope: |
| 84 | Location | hooks.md:156 | hook-events | HOOK-CANDIDATE | Scope |
| 85 | Matcher patterns | hooks.md:167 | hook-events | HOOK-CANDIDATE | The `matcher` field is a regex string that filters when hooks fire. Use `"*"`, `""`,... |
| 86 | Match MCP tools | hooks.md:213 | hook-events | HOOK-CANDIDATE | [MCP](/en/mcp) server tools appear as regular tools in tool events (`PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`), so... |
| 87 | Hook handler fields | hooks.md:257 | hook-events | HOOK-CANDIDATE | Each object in the inner `hooks` array is a hook handler: the shell command, HTTP... |
| 88 | Common fields | hooks.md:266 | hook-events | HOOK-CANDIDATE | These fields apply to all hook types: |
| 89 | Field | hooks.md:270 | hook-events | HOOK-CANDIDATE | Required |
| 90 | Command hook fields | hooks.md:277 | hook-events | HOOK-CANDIDATE | In addition to the [common fields](#common-fields), command hooks accept these fields: |
| 91 | HTTP hook fields | hooks.md:287 | hook-events | HOOK-CANDIDATE | In addition to the [common fields](#common-fields), HTTP hooks accept these fields: |
| 92 | Prompt and agent hook fields | hooks.md:326 | hook-events | HOOK-CANDIDATE | In addition to the [common fields](#common-fields), prompt and agent hooks accept these fields: |
| 93 | Reference scripts by path | hooks.md:337 | hook-events | HOOK-CANDIDATE | Use environment variables to reference hook scripts relative to the project or plugin root, regardless... |
| 94 | Hooks in skills and agents | hooks.md:397 | hook-events | HOOK-CANDIDATE | In addition to settings files and plugins, hooks can be defined directly in [skills](/en/skills) and... |
| 95 | The `/hooks` menu | hooks.md:422 | hook-events | HOOK-CANDIDATE | Type `/hooks` in Claude Code to open a read-only browser for your configured hooks. The... |
| 96 | Disable or remove hooks | hooks.md:437 | hook-events | HOOK-CANDIDATE | To remove a hook, delete its entry from the settings JSON file. |
| 97 | Common input fields | hooks.md:451 | hook-events | HOOK-CANDIDATE | Hook events receive these fields as JSON, in addition to event-specific fields documented in each... |
| 98 | Exit code output | hooks.md:488 | hook-events | HOOK-CANDIDATE | The exit code from your hook command tells Claude Code whether the action should proceed,... |
| 99 | Exit code 2 behavior per event | hooks.md:513 | hook-events | HOOK-CANDIDATE | Exit code 2 is the way a hook signals "stop, don't do this." The effect... |
| 100 | HTTP response handling | hooks.md:544 | hook-events | HOOK-CANDIDATE | HTTP hooks use HTTP status codes and response bodies instead of exit codes and stdout: |
| 101 | JSON output | hooks.md:556 | hook-events | HOOK-CANDIDATE | Exit codes let you allow or block, but JSON output gives you finer-grained control. Instead... |
| 102 | Decision control | hooks.md:585 | hook-events | HOOK-CANDIDATE | Not every event supports blocking or controlling behavior through JSON. The events that do each... |
| 103 | Events | hooks.md:589 | hook-events | HOOK-CANDIDATE | Decision pattern |
| 104 | Matcher | hooks.md:661 | hook-events | HOOK-CANDIDATE | When it fires |
| 105 | SessionStart input | hooks.md:668 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), SessionStart hooks receive `source`, `model`, and optionally `agent_type`.... |
| 106 | SessionStart decision control | hooks.md:683 | hook-events | HOOK-CANDIDATE | Any text your hook script prints to stdout is added as context for Claude. In... |
| 107 | Persist environment variables | hooks.md:700 | hook-events | HOOK-CANDIDATE | SessionStart hooks have access to the `CLAUDE_ENV_FILE` environment variable, which provides a file path where... |
| 108 | InstructionsLoaded input | hooks.md:749 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), InstructionsLoaded hooks receive these fields: |
| 109 | InstructionsLoaded decision control | hooks.md:774 | hook-events | HOOK-CANDIDATE | InstructionsLoaded hooks have no decision control. They cannot block or modify instruction loading. Use this... |
| 110 | UserPromptSubmit input | hooks.md:784 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), UserPromptSubmit hooks receive the `prompt` field containing the... |
| 111 | UserPromptSubmit decision control | hooks.md:799 | hook-events | HOOK-CANDIDATE | `UserPromptSubmit` hooks can control whether a user prompt is processed and add context. All [JSON... |
| 112 | PreToolUse input | hooks.md:840 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), PreToolUse hooks receive `tool_name`, `tool_input`, and `tool_use_id`. The... |
| 113 | PreToolUse decision control | hooks.md:937 | hook-events | HOOK-CANDIDATE | `PreToolUse` hooks can control whether a tool call proceeds. Unlike other hooks that use a... |
| 114 | PermissionRequest input | hooks.md:975 | hook-events | HOOK-CANDIDATE | PermissionRequest hooks receive `tool_name` and `tool_input` fields like PreToolUse hooks, but without `tool_use_id`. An optional... |
| 115 | PermissionRequest decision control | hooks.md:1002 | hook-events | HOOK-CANDIDATE | `PermissionRequest` hooks can allow or deny permission requests. In addition to the [JSON output fields](#json-output)... |
| 116 | Permission update entries | hooks.md:1028 | hook-events | HOOK-CANDIDATE | The `updatedPermissions` output field and the [`permission_suggestions` input field](#permissionrequest-input) both use the same array of... |
| 117 | PostToolUse input | hooks.md:1058 | hook-events | HOOK-CANDIDATE | `PostToolUse` hooks fire after a tool has already executed successfully. The input includes both `tool_input`,... |
| 118 | PostToolUse decision control | hooks.md:1082 | hook-events | HOOK-CANDIDATE | `PostToolUse` hooks can provide feedback to Claude after tool execution. In addition to the [JSON... |
| 119 | PostToolUseFailure input | hooks.md:1110 | hook-events | HOOK-CANDIDATE | PostToolUseFailure hooks receive the same `tool_name` and `tool_input` fields as PostToolUse, along with error information... |
| 120 | PostToolUseFailure decision control | hooks.md:1137 | hook-events | HOOK-CANDIDATE | `PostToolUseFailure` hooks can provide context to Claude after a tool failure. In addition to the... |
| 121 | Notification input | hooks.md:1187 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), Notification hooks receive `message` with the notification text,... |
| 122 | SubagentStart input | hooks.md:1213 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), SubagentStart hooks receive `agent_id` with the unique identifier... |
| 123 | SubagentStop input | hooks.md:1247 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), SubagentStop hooks receive `stop_hook_active`, `agent_id`, `agent_type`, `agent_transcript_path`, and... |
| 124 | Stop input | hooks.md:1274 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), Stop hooks receive `stop_hook_active` and `last_assistant_message`. The `stop_hook_active`... |
| 125 | Stop decision control | hooks.md:1290 | hook-events | HOOK-CANDIDATE | `Stop` and `SubagentStop` hooks can control whether Claude continues. In addition to the [JSON output... |
| 126 | StopFailure input | hooks.md:1310 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), StopFailure hooks receive `error`, optional `error_details`, and optional... |
| 127 | TeammateIdle input | hooks.md:1340 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), TeammateIdle hooks receive `teammate_name` and `team_name`. |
| 128 | TeammateIdle decision control | hooks.md:1361 | hook-events | HOOK-CANDIDATE | TeammateIdle hooks support two ways to control teammate behavior: |
| 129 | TaskCompleted input | hooks.md:1387 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), TaskCompleted hooks receive `task_id`, `task_subject`, and optionally `task_description`,... |
| 130 | TaskCompleted decision control | hooks.md:1414 | hook-events | HOOK-CANDIDATE | TaskCompleted hooks support two ways to control task completion: |
| 131 | ConfigChange input | hooks.md:1472 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), ConfigChange hooks receive `source` and optionally `file_path`. The... |
| 132 | ConfigChange decision control | hooks.md:1487 | hook-events | HOOK-CANDIDATE | ConfigChange hooks can block configuration changes from taking effect. Use exit code 2 or a... |
| 133 | CwdChanged input | hooks.md:1513 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), CwdChanged hooks receive `old_cwd` and `new_cwd`. |
| 134 | CwdChanged output | hooks.md:1528 | hook-events | HOOK-CANDIDATE | In addition to the [JSON output fields](#json-output) available to all hooks, CwdChanged hooks can return... |
| 135 | FileChanged input | hooks.md:1544 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), FileChanged hooks receive `file_path` and `event`. |
| 136 | FileChanged output | hooks.md:1564 | hook-events | HOOK-CANDIDATE | In addition to the [JSON output fields](#json-output) available to all hooks, FileChanged hooks can return... |
| 137 | WorktreeCreate input | hooks.md:1601 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), WorktreeCreate hooks receive the `name` field. This is... |
| 138 | WorktreeCreate output | hooks.md:1615 | hook-events | HOOK-CANDIDATE | WorktreeCreate hooks do not use the standard allow/block decision model. Instead, the hook's success or... |
| 139 | WorktreeRemove input | hooks.md:1647 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), WorktreeRemove hooks receive the `worktree_path` field, which is... |
| 140 | PreCompact input | hooks.md:1674 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), PreCompact hooks receive `trigger` and `custom_instructions`. For `manual`,... |
| 141 | PostCompact input | hooks.md:1700 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), PostCompact hooks receive `trigger` and `compact_summary`. The `compact_summary`... |
| 142 | Reason | hooks.md:1724 | hook-events | HOOK-CANDIDATE | Description |
| 143 | SessionEnd input | hooks.md:1733 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), SessionEnd hooks receive a `reason` field indicating why... |
| 144 | Elicitation input | hooks.md:1761 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), Elicitation hooks receive `mcp_server_name`, `message`, and optional `mode`,... |
| 145 | Elicitation output | hooks.md:1802 | hook-events | HOOK-CANDIDATE | To respond programmatically without showing the dialog, return a JSON object with `hookSpecificOutput`: |
| 146 | ElicitationResult input | hooks.md:1831 | hook-events | HOOK-CANDIDATE | In addition to the [common input fields](#common-input-fields), ElicitationResult hooks receive `mcp_server_name`, `action`, and optional `mode`,... |
| 147 | ElicitationResult output | hooks.md:1850 | hook-events | HOOK-CANDIDATE | To override the user's response, return a JSON object with `hookSpecificOutput`: |
| 148 | How prompt-based hooks work | hooks.md:1906 | hook-events | HOOK-CANDIDATE | Instead of executing a Bash command, prompt-based hooks: |
| 149 | Prompt hook configuration | hooks.md:1914 | hook-events | HOOK-CANDIDATE | Set `type` to `"prompt"` and provide a `prompt` string instead of a `command`. Use the... |
| 150 | Response schema | hooks.md:1944 | hook-events | HOOK-CANDIDATE | The LLM must respond with JSON containing: |
| 151 | Example: Multi-criteria Stop hook | hooks.md:1960 | hook-events | HOOK-CANDIDATE | This `Stop` hook uses a detailed prompt to check three conditions before allowing Claude to... |
| 152 | How agent hooks work | hooks.md:1986 | hook-events | HOOK-CANDIDATE | When an agent hook fires: |
| 153 | Agent hook configuration | hooks.md:1997 | hook-events | HOOK-CANDIDATE | Set `type` to `"agent"` and provide a `prompt` string. The configuration fields are the same... |
| 154 | Configure an async hook | hooks.md:2034 | hook-events | HOOK-CANDIDATE | Add `"async": true` to a command hook's configuration to run it in the background without... |
| 155 | How async hooks execute | hooks.md:2062 | hook-events | HOOK-CANDIDATE | When an async hook fires, Claude Code starts the hook process and immediately continues without... |
| 156 | Example: run tests after file changes | hooks.md:2070 | hook-events | HOOK-CANDIDATE | This hook starts a test suite in the background whenever Claude writes a file, then... |
| 157 | Limitations | hooks.md:2120 | hook-events | HOOK-CANDIDATE | Async hooks have several constraints compared to synchronous hooks: |
| 158 | Disclaimer | hooks.md:2131 | hook-events | HOOK-CANDIDATE | Command hooks run with your system user's full permissions. |
| 159 | Security best practices | hooks.md:2139 | hook-events | HOOK-CANDIDATE | Keep these practices in mind when writing hooks: |
| 160 | Bundled skills | skills.md:19 | skills | SKILL-CANDIDATE | Bundled skills ship with Claude Code and are available in every session. Unlike [built-in commands](/en/commands),... |
| 161 | /batch <instruction> | skills.md:27 | skills | SKILL-CANDIDATE | Orchestrate large-scale changes across a codebase in parallel. Researches the codebase, decomposes the work into... |
| 162 | /claude-api | skills.md:28 | skills | SKILL-CANDIDATE | Load Claude API reference material for your project's language (Python, TypeScript, Java, Go, Ruby, C#,... |
| 163 | /debug [description] | skills.md:29 | skills | SKILL-CANDIDATE | Enable debug logging for the current session and troubleshoot issues by reading the session debug... |
| 164 | /loop [interval] <prompt> | skills.md:30 | skills | SKILL-CANDIDATE | Run a prompt repeatedly on an interval while the session stays open. Useful for polling... |
| 165 | /simplify [focus] | skills.md:31 | skills | SKILL-CANDIDATE | Review your recently changed files for code reuse, quality, and efficiency issues, then fix them.... |
| 166 | Getting started | skills.md:33 | skills | SKILL-CANDIDATE | ### Create your first skill |
| 167 | Create your first skill | skills.md:35 | skills | SKILL-CANDIDATE | This example creates a skill that teaches Claude to explain code using visual diagrams and... |
| 168 | Where skills live | skills.md:89 | skills | SKILL-CANDIDATE | Where you store a skill determines who can use it: |
| 169 | Configure skills | skills.md:132 | skills | SKILL-CANDIDATE | Skills are configured through YAML frontmatter at the top of `SKILL.md` and the markdown content... |
| 170 | Types of skill content | skills.md:136 | skills | SKILL-CANDIDATE | Skill files can contain any instructions, but thinking about how you want to invoke them... |
| 171 | Frontmatter reference | skills.md:172 | skills | SKILL-CANDIDATE | Beyond the markdown content, you can configure skill behavior using YAML frontmatter fields between `---`... |
| 172 | name | skills.md:191 | skills | SKILL-CANDIDATE | No |
| 173 | description | skills.md:192 | skills | SKILL-CANDIDATE | Recommended |
| 174 | argument-hint | skills.md:193 | skills | SKILL-CANDIDATE | No |
| 175 | disable-model-invocation | skills.md:194 | skills | SKILL-CANDIDATE | No |
| 176 | user-invocable | skills.md:195 | skills | SKILL-CANDIDATE | No |
| 177 | allowed-tools | skills.md:196 | skills | SKILL-CANDIDATE | No |
| 178 | model | skills.md:197 | skills | SKILL-CANDIDATE | No |
| 179 | effort | skills.md:198 | skills | SKILL-CANDIDATE | No |
| 180 | context | skills.md:199 | skills | SKILL-CANDIDATE | No |
| 181 | agent | skills.md:200 | skills | SKILL-CANDIDATE | No |
| 182 | hooks | skills.md:201 | skills | SKILL-CANDIDATE | No |
| 183 | shell | skills.md:202 | skills | SKILL-CANDIDATE | No |
| 184 | $ARGUMENTS | skills.md:210 | skills | SKILL-CANDIDATE | All arguments passed when invoking the skill. If `$ARGUMENTS` is not present in the content,... |
| 185 | $ARGUMENTS[N] | skills.md:211 | skills | SKILL-CANDIDATE | Access a specific argument by 0-based index, such as `$ARGUMENTS[0]` for the first argument. |
| 186 | $N | skills.md:212 | skills | SKILL-CANDIDATE | Shorthand for `$ARGUMENTS[N]`, such as `$0` for the first argument or `$1` for the second. |
| 187 | ${CLAUDE_SESSION_ID} | skills.md:213 | skills | SKILL-CANDIDATE | The current session ID. Useful for logging, creating session-specific files, or correlating skill output with... |
| 188 | ${CLAUDE_SKILL_DIR} | skills.md:214 | skills | SKILL-CANDIDATE | The directory containing the skill's `SKILL.md` file. For plugin skills, this is the skill's subdirectory... |
| 189 | Add supporting files | skills.md:229 | skills | SKILL-CANDIDATE | Skills can include multiple files in their directory. This keeps `SKILL.md` focused on the essentials... |
| 190 | Additional resources | skills.md:245 | skills | SKILL-CANDIDATE | - For complete API details, see [reference.md](reference.md) |
| 191 | Control who invokes a skill | skills.md:253 | skills | SKILL-CANDIDATE | By default, both you and Claude can invoke any skill. You can type `/skill-name` to... |
| 192 | disable-model-invocation: true | skills.md:283 | skills | SKILL-CANDIDATE | Yes |
| 193 | user-invocable: false | skills.md:284 | skills | SKILL-CANDIDATE | No |
| 194 | Restrict tool access | skills.md:290 | skills | SKILL-CANDIDATE | Use the `allowed-tools` field to limit which tools Claude can use when a skill is... |
| 195 | Pass arguments to skills | skills.md:302 | skills | SKILL-CANDIDATE | Both you and Claude can pass arguments when invoking a skill. Arguments are available via... |
| 196 | Advanced patterns | skills.md:352 | skills | SKILL-CANDIDATE | ### Inject dynamic context |
| 197 | Inject dynamic context | skills.md:354 | skills | SKILL-CANDIDATE | The `` !`<command>` `` syntax runs shell commands before the skill content is sent to... |
| 198 | Pull request context | skills.md:369 | skills | SKILL-CANDIDATE | - PR diff: !`gh pr diff` |
| 199 | Your task | skills.md:374 | skills | SKILL-CANDIDATE | Summarize this pull request... |
| 200 | Run skills in a subagent | skills.md:390 | skills | SKILL-CANDIDATE | Add `context: fork` to your frontmatter when you want a skill to run in isolation.... |
| 201 | context: fork | skills.md:402 | skills | SKILL-CANDIDATE | From agent type (`Explore`, `Plan`, etc.) |
| 202 | skills | skills.md:403 | skills | SKILL-CANDIDATE | Subagent's markdown body |
| 203 | Restrict Claude's skill access | skills.md:435 | skills | SKILL-CANDIDATE | By default, Claude can invoke any skill that doesn't have `disable-model-invocation: true` set. Skills that... |
| 204 | Share skills | skills.md:467 | skills | SKILL-CANDIDATE | Skills can be distributed at different scopes depending on your audience: |
| 205 | Generate visual output | skills.md:475 | skills | SKILL-CANDIDATE | Skills can bundle and run scripts in any language, giving Claude capabilities beyond what's possible... |
| 206 | Usage | skills.md:500 | skills | SKILL-CANDIDATE | Run the visualization script from your project root: |
| 207 | What the visualization shows | skills.md:510 | skills | SKILL-CANDIDATE | - Collapsible directories: Click folders to expand/collapse |
| 208 | Troubleshooting | skills.md:664 | skills | SKILL-CANDIDATE | ### Skill not triggering |
| 209 | Skill not triggering | skills.md:666 | skills | SKILL-CANDIDATE | If Claude doesn't use your skill when expected: |
| 210 | Skill triggers too often | skills.md:675 | skills | SKILL-CANDIDATE | If Claude uses your skill when you don't want it: |
| 211 | Claude doesn't see all my skills | skills.md:682 | skills | SKILL-CANDIDATE | Skill descriptions are loaded into context so Claude knows what's available. If you have many... |
| 212 | Tool | tools-reference.md:11 | tools | COMMAND-CANDIDATE | Description |
| 213 | Agent | tools-reference.md:13 | tools | COMMAND-CANDIDATE | Spawns a [subagent](/en/sub-agents) with its own context window to handle a task |
| 214 | AskUserQuestion | tools-reference.md:14 | tools | COMMAND-CANDIDATE | Asks multiple-choice questions to gather requirements or clarify ambiguity |
| 215 | Bash | tools-reference.md:15 | tools | COMMAND-CANDIDATE | Executes shell commands in your environment. See [Bash tool behavior](#bash-tool-behavior) |
| 216 | CronCreate | tools-reference.md:16 | tools | COMMAND-CANDIDATE | Schedules a recurring or one-shot prompt within the current session (gone when Claude exits). See... |
| 217 | CronDelete | tools-reference.md:17 | tools | COMMAND-CANDIDATE | Cancels a scheduled task by ID |
| 218 | CronList | tools-reference.md:18 | tools | COMMAND-CANDIDATE | Lists all scheduled tasks in the session |
| 219 | Edit | tools-reference.md:19 | tools | COMMAND-CANDIDATE | Makes targeted edits to specific files |
| 220 | EnterPlanMode | tools-reference.md:20 | tools | COMMAND-CANDIDATE | Switches to plan mode to design an approach before coding |
| 221 | EnterWorktree | tools-reference.md:21 | tools | COMMAND-CANDIDATE | Creates an isolated [git worktree](/en/common-workflows#run-parallel-claude-code-sessions-with-git-worktrees) and switches into it |
| 222 | ExitPlanMode | tools-reference.md:22 | tools | COMMAND-CANDIDATE | Presents a plan for approval and exits plan mode |
| 223 | ExitWorktree | tools-reference.md:23 | tools | COMMAND-CANDIDATE | Exits a worktree session and returns to the original directory |
| 224 | Glob | tools-reference.md:24 | tools | COMMAND-CANDIDATE | Finds files based on pattern matching |
| 225 | Grep | tools-reference.md:25 | tools | COMMAND-CANDIDATE | Searches for patterns in file contents |
| 226 | ListMcpResourcesTool | tools-reference.md:26 | tools | COMMAND-CANDIDATE | Lists resources exposed by connected [MCP servers](/en/mcp) |
| 227 | LSP | tools-reference.md:27 | tools | COMMAND-CANDIDATE | Code intelligence via language servers. Reports type errors and warnings automatically after file edits. Also... |
| 228 | NotebookEdit | tools-reference.md:28 | tools | COMMAND-CANDIDATE | Modifies Jupyter notebook cells |
| 229 | PowerShell | tools-reference.md:29 | tools | COMMAND-CANDIDATE | Executes PowerShell commands on Windows. Opt-in preview. See [PowerShell tool](#powershell-tool) |
| 230 | Read | tools-reference.md:30 | tools | COMMAND-CANDIDATE | Reads the contents of files |
| 231 | ReadMcpResourceTool | tools-reference.md:31 | tools | COMMAND-CANDIDATE | Reads a specific MCP resource by URI |
| 232 | Skill | tools-reference.md:32 | tools | COMMAND-CANDIDATE | Executes a [skill](/en/skills#control-who-invokes-a-skill) within the main conversation |
| 233 | TaskCreate | tools-reference.md:33 | tools | COMMAND-CANDIDATE | Creates a new task in the task list |
| 234 | TaskGet | tools-reference.md:34 | tools | COMMAND-CANDIDATE | Retrieves full details for a specific task |
| 235 | TaskList | tools-reference.md:35 | tools | COMMAND-CANDIDATE | Lists all tasks with their current status |
| 236 | TaskOutput | tools-reference.md:36 | tools | COMMAND-CANDIDATE | (Deprecated) Retrieves output from a background task. Prefer `Read` on the task's output file path |
| 237 | TaskStop | tools-reference.md:37 | tools | COMMAND-CANDIDATE | Kills a running background task by ID |
| 238 | TaskUpdate | tools-reference.md:38 | tools | COMMAND-CANDIDATE | Updates task status, dependencies, details, or deletes tasks |
| 239 | TodoWrite | tools-reference.md:39 | tools | COMMAND-CANDIDATE | Manages the session task checklist. Available in non-interactive mode and the [Agent SDK](/en/headless); interactive sessions... |
| 240 | ToolSearch | tools-reference.md:40 | tools | COMMAND-CANDIDATE | Searches for and loads deferred tools when [tool search](/en/mcp#scale-with-mcp-tool-search) is enabled |
| 241 | WebFetch | tools-reference.md:41 | tools | COMMAND-CANDIDATE | Fetches content from a specified URL |
| 242 | WebSearch | tools-reference.md:42 | tools | COMMAND-CANDIDATE | Performs web searches |
| 243 | Write | tools-reference.md:43 | tools | COMMAND-CANDIDATE | Creates or overwrites files |
| 244 | Bash tool behavior | tools-reference.md:47 | tools | COMMAND-CANDIDATE | The Bash tool runs each command in a separate process with the following persistence behavior: |
| 245 | PowerShell tool | tools-reference.md:56 | tools | COMMAND-CANDIDATE | On Windows, Claude Code can run PowerShell commands natively instead of routing through Git Bash.... |
| 246 | Enable the PowerShell tool | tools-reference.md:60 | tools | COMMAND-CANDIDATE | Set `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` in your environment or in `settings.json`: |
| 247 | Shell selection in settings, hooks, and skills | tools-reference.md:74 | tools | COMMAND-CANDIDATE | Three additional settings control where PowerShell is used: |
| 248 | Preview limitations | tools-reference.md:82 | tools | COMMAND-CANDIDATE | The PowerShell tool has the following known limitations during the preview: |
| 249 | capabilities.experimental['claude/channel'] | channels-reference.md:190 | channels | NEEDS-REVIEW | `object` |
| 250 | capabilities.experimental['claude/channel/permission'] | channels-reference.md:191 | channels | NEEDS-REVIEW | `object` |
| 251 | How checkpoints work | checkpointing.md:11 | checkpointing | NEEDS-REVIEW | As you work with Claude, checkpointing automatically captures the state of your code before each... |
| 252 | ANTHROPIC_API_KEY | env-vars.md:13 | env-vars | RULE-CANDIDATE | API key sent as `X-Api-Key` header. When set, this key is used instead of your... |
| 253 | ANTHROPIC_AUTH_TOKEN | env-vars.md:14 | env-vars | RULE-CANDIDATE | Custom value for the `Authorization` header (the value you set here will be prefixed with... |
| 254 | ANTHROPIC_BASE_URL | env-vars.md:15 | env-vars | RULE-CANDIDATE | Override the API endpoint to route requests through a proxy or gateway. When set to... |
| 255 | ANTHROPIC_CUSTOM_HEADERS | env-vars.md:16 | env-vars | RULE-CANDIDATE | Custom headers to add to requests (`Name: Value` format, newline-separated for multiple headers) |
| 256 | ANTHROPIC_CUSTOM_MODEL_OPTION | env-vars.md:17 | env-vars | RULE-CANDIDATE | Model ID to add as a custom entry in the `/model` picker. Use this to... |
| 257 | ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION | env-vars.md:18 | env-vars | RULE-CANDIDATE | Display description for the custom model entry in the `/model` picker. Defaults to `Custom model... |
| 258 | ANTHROPIC_CUSTOM_MODEL_OPTION_NAME | env-vars.md:19 | env-vars | RULE-CANDIDATE | Display name for the custom model entry in the `/model` picker. Defaults to the model... |
| 259 | ANTHROPIC_DEFAULT_HAIKU_MODEL | env-vars.md:20 | env-vars | RULE-CANDIDATE | See [Model configuration](/en/model-config#environment-variables) |
| 260 | ANTHROPIC_DEFAULT_HAIKU_MODEL_DESCRIPTION | env-vars.md:21 | env-vars | RULE-CANDIDATE | See [Model configuration](/en/model-config#customize-pinned-model-display-and-capabilities) |
| 261 | ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME | env-vars.md:22 | env-vars | RULE-CANDIDATE | See [Model configuration](/en/model-config#customize-pinned-model-display-and-capabilities) |
| 262 | ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES | env-vars.md:23 | env-vars | RULE-CANDIDATE | See [Model configuration](/en/model-config#customize-pinned-model-display-and-capabilities) |
| 263 | ANTHROPIC_DEFAULT_OPUS_MODEL | env-vars.md:24 | env-vars | RULE-CANDIDATE | See [Model configuration](/en/model-config#environment-variables) |
| 264 | ANTHROPIC_DEFAULT_OPUS_MODEL_DESCRIPTION | env-vars.md:25 | env-vars | RULE-CANDIDATE | See [Model configuration](/en/model-config#customize-pinned-model-display-and-capabilities) |
| 265 | ANTHROPIC_DEFAULT_OPUS_MODEL_NAME | env-vars.md:26 | env-vars | RULE-CANDIDATE | See [Model configuration](/en/model-config#customize-pinned-model-display-and-capabilities) |
| 266 | ANTHROPIC_DEFAULT_OPUS_MODEL_SUPPORTED_CAPABILITIES | env-vars.md:27 | env-vars | RULE-CANDIDATE | See [Model configuration](/en/model-config#customize-pinned-model-display-and-capabilities) |
| 267 | ANTHROPIC_DEFAULT_SONNET_MODEL | env-vars.md:28 | env-vars | RULE-CANDIDATE | See [Model configuration](/en/model-config#environment-variables) |
| 268 | ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION | env-vars.md:29 | env-vars | RULE-CANDIDATE | See [Model configuration](/en/model-config#customize-pinned-model-display-and-capabilities) |
| 269 | ANTHROPIC_DEFAULT_SONNET_MODEL_NAME | env-vars.md:30 | env-vars | RULE-CANDIDATE | See [Model configuration](/en/model-config#customize-pinned-model-display-and-capabilities) |
| 270 | ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES | env-vars.md:31 | env-vars | RULE-CANDIDATE | See [Model configuration](/en/model-config#customize-pinned-model-display-and-capabilities) |
| 271 | ANTHROPIC_FOUNDRY_API_KEY | env-vars.md:32 | env-vars | RULE-CANDIDATE | API key for Microsoft Foundry authentication (see [Microsoft Foundry](/en/microsoft-foundry)) |
| 272 | ANTHROPIC_FOUNDRY_BASE_URL | env-vars.md:33 | env-vars | RULE-CANDIDATE | Full base URL for the Foundry resource (for example, `https://my-resource.services.ai.azure.com/anthropic`). Alternative to `ANTHROPIC_FOUNDRY_RESOURCE` (see [Microsoft... |
| 273 | ANTHROPIC_FOUNDRY_RESOURCE | env-vars.md:34 | env-vars | RULE-CANDIDATE | Foundry resource name (for example, `my-resource`). Required if `ANTHROPIC_FOUNDRY_BASE_URL` is not set (see [Microsoft Foundry](/en/microsoft-foundry)) |
| 274 | ANTHROPIC_MODEL | env-vars.md:35 | env-vars | RULE-CANDIDATE | Name of the model setting to use (see [Model Configuration](/en/model-config#environment-variables)) |
| 275 | ANTHROPIC_SMALL_FAST_MODEL | env-vars.md:36 | env-vars | RULE-CANDIDATE | \[DEPRECATED] Name of [Haiku-class model for background tasks](/en/costs) |
| 276 | ANTHROPIC_SMALL_FAST_MODEL_AWS_REGION | env-vars.md:37 | env-vars | RULE-CANDIDATE | Override AWS region for the Haiku-class model when using Bedrock |
| 277 | AWS_BEARER_TOKEN_BEDROCK | env-vars.md:38 | env-vars | RULE-CANDIDATE | Bedrock API key for authentication (see [Bedrock API keys](https://aws.amazon.com/blogs/machine-learning/accelerate-ai-development-with-amazon-bedrock-api-keys/)) |
| 278 | BASH_DEFAULT_TIMEOUT_MS | env-vars.md:39 | env-vars | RULE-CANDIDATE | Default timeout for long-running bash commands |
| 279 | BASH_MAX_OUTPUT_LENGTH | env-vars.md:40 | env-vars | RULE-CANDIDATE | Maximum number of characters in bash outputs before they are middle-truncated |
| 280 | BASH_MAX_TIMEOUT_MS | env-vars.md:41 | env-vars | RULE-CANDIDATE | Maximum timeout the model can set for long-running bash commands |
| 281 | CLAUDECODE | env-vars.md:42 | env-vars | RULE-CANDIDATE | Set to `1` in shell environments Claude Code spawns (Bash tool, tmux sessions). Not set... |
| 282 | CLAUDE_AUTOCOMPACT_PCT_OVERRIDE | env-vars.md:43 | env-vars | RULE-CANDIDATE | Set the percentage of context capacity (1-100) at which auto-compaction triggers. By default, auto-compaction triggers... |
| 283 | CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR | env-vars.md:44 | env-vars | RULE-CANDIDATE | Return to the original working directory after each Bash command |
| 284 | CLAUDE_CODE_ACCOUNT_UUID | env-vars.md:45 | env-vars | RULE-CANDIDATE | Account UUID for the authenticated user. Used by SDK callers to provide account information synchronously,... |
| 285 | CLAUDE_CODE_ADDITIONAL_DIRECTORIES_CLAUDE_MD | env-vars.md:46 | env-vars | RULE-CANDIDATE | Set to `1` to load CLAUDE.md files from directories specified with `--add-dir`. By default, additional... |
| 286 | CLAUDE_CODE_AUTO_COMPACT_WINDOW | env-vars.md:47 | env-vars | RULE-CANDIDATE | Set the context capacity in tokens used for auto-compaction calculations. Defaults to the model's context... |
| 287 | CLAUDE_CODE_API_KEY_HELPER_TTL_MS | env-vars.md:48 | env-vars | RULE-CANDIDATE | Interval in milliseconds at which credentials should be refreshed (when using [`apiKeyHelper`](/en/settings#available-settings)) |
| 288 | CLAUDE_CODE_CLIENT_CERT | env-vars.md:49 | env-vars | RULE-CANDIDATE | Path to client certificate file for mTLS authentication |
| 289 | CLAUDE_CODE_CLIENT_KEY | env-vars.md:50 | env-vars | RULE-CANDIDATE | Path to client private key file for mTLS authentication |
| 290 | CLAUDE_CODE_CLIENT_KEY_PASSPHRASE | env-vars.md:51 | env-vars | RULE-CANDIDATE | Passphrase for encrypted CLAUDE\_CODE\_CLIENT\_KEY (optional) |
| 291 | CLAUDE_CODE_DISABLE_1M_CONTEXT | env-vars.md:52 | env-vars | RULE-CANDIDATE | Set to `1` to disable [1M context window](/en/model-config#extended-context) support. When set, 1M model variants are... |
| 292 | CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING | env-vars.md:53 | env-vars | RULE-CANDIDATE | Set to `1` to disable [adaptive reasoning](/en/model-config#adjust-effort-level) for Opus 4.6 and Sonnet 4.6. When disabled,... |
| 293 | CLAUDE_CODE_DISABLE_AUTO_MEMORY | env-vars.md:54 | env-vars | RULE-CANDIDATE | Set to `1` to disable [auto memory](/en/memory#auto-memory). Set to `0` to force auto memory on... |
| 294 | CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS | env-vars.md:55 | env-vars | RULE-CANDIDATE | Set to `1` to remove built-in commit and PR workflow instructions and the git status... |
| 295 | CLAUDE_CODE_DISABLE_BACKGROUND_TASKS | env-vars.md:56 | env-vars | RULE-CANDIDATE | Set to `1` to disable all background task functionality, including the `run_in_background` parameter on Bash... |
| 296 | CLAUDE_CODE_DISABLE_CRON | env-vars.md:57 | env-vars | RULE-CANDIDATE | Set to `1` to disable [scheduled tasks](/en/scheduled-tasks). The `/loop` skill and cron tools become unavailable... |
| 297 | CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS | env-vars.md:58 | env-vars | RULE-CANDIDATE | Set to `1` to strip Anthropic-specific `anthropic-beta` request headers and beta tool-schema fields (such as... |
| 298 | CLAUDE_CODE_DISABLE_FAST_MODE | env-vars.md:59 | env-vars | RULE-CANDIDATE | Set to `1` to disable [fast mode](/en/fast-mode) |
| 299 | CLAUDE_CODE_DISABLE_FEEDBACK_SURVEY | env-vars.md:60 | env-vars | RULE-CANDIDATE | Set to `1` to disable the "How is Claude doing?" session quality surveys. Surveys are... |
| 300 | CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC | env-vars.md:61 | env-vars | RULE-CANDIDATE | Equivalent of setting `DISABLE_AUTOUPDATER`, `DISABLE_FEEDBACK_COMMAND`, `DISABLE_ERROR_REPORTING`, and `DISABLE_TELEMETRY` |
| 301 | CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK | env-vars.md:62 | env-vars | RULE-CANDIDATE | Set to `1` to disable the non-streaming fallback when a streaming request fails mid-stream. Streaming... |
| 302 | CLAUDE_CODE_DISABLE_TERMINAL_TITLE | env-vars.md:63 | env-vars | RULE-CANDIDATE | Set to `1` to disable automatic terminal title updates based on conversation context |
| 303 | CLAUDE_CODE_EFFORT_LEVEL | env-vars.md:64 | env-vars | RULE-CANDIDATE | Set the effort level for supported models. Values: `low`, `medium`, `high`, `max` (Opus 4.6 only),... |
| 304 | CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION | env-vars.md:65 | env-vars | RULE-CANDIDATE | Set to `false` to disable prompt suggestions (the "Prompt suggestions" toggle in `/config`). These are... |
| 305 | CLAUDE_CODE_ENABLE_TASKS | env-vars.md:66 | env-vars | RULE-CANDIDATE | Set to `true` to enable the task tracking system in non-interactive mode (the `-p` flag).... |
| 306 | CLAUDE_CODE_ENABLE_TELEMETRY | env-vars.md:67 | env-vars | RULE-CANDIDATE | Set to `1` to enable OpenTelemetry data collection for metrics and logging. Required before configuring... |
| 307 | CLAUDE_CODE_EXIT_AFTER_STOP_DELAY | env-vars.md:68 | env-vars | RULE-CANDIDATE | Time in milliseconds to wait after the query loop becomes idle before automatically exiting. Useful... |
| 308 | CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS | env-vars.md:69 | env-vars | RULE-CANDIDATE | Set to `1` to enable [agent teams](/en/agent-teams). Agent teams are experimental and disabled by default |
| 309 | CLAUDE_CODE_FILE_READ_MAX_OUTPUT_TOKENS | env-vars.md:70 | env-vars | RULE-CANDIDATE | Override the default token limit for file reads. Useful when you need to read larger... |
| 310 | CLAUDE_CODE_IDE_SKIP_AUTO_INSTALL | env-vars.md:71 | env-vars | RULE-CANDIDATE | Skip auto-installation of IDE extensions. Equivalent to setting [`autoInstallIdeExtension`](/en/settings#global-config-settings) to `false` |
| 311 | CLAUDE_CODE_MAX_OUTPUT_TOKENS | env-vars.md:72 | env-vars | RULE-CANDIDATE | Set the maximum number of output tokens for most requests. Defaults and caps vary by... |
| 312 | CLAUDE_CODE_NEW_INIT | env-vars.md:73 | env-vars | RULE-CANDIDATE | Set to `true` to make `/init` run an interactive setup flow. The flow asks which... |
| 313 | CLAUDE_CODE_ORGANIZATION_UUID | env-vars.md:74 | env-vars | RULE-CANDIDATE | Organization UUID for the authenticated user. Used by SDK callers to provide account information synchronously.... |
| 314 | CLAUDE_CODE_OTEL_HEADERS_HELPER_DEBOUNCE_MS | env-vars.md:75 | env-vars | RULE-CANDIDATE | Interval for refreshing dynamic OpenTelemetry headers in milliseconds (default: 1740000 / 29 minutes). See [Dynamic... |
| 315 | CLAUDE_CODE_PLAN_MODE_REQUIRED | env-vars.md:76 | env-vars | RULE-CANDIDATE | Auto-set to `true` on [agent team](/en/agent-teams) teammates that require plan approval. Read-only: set by Claude... |
| 316 | CLAUDE_CODE_PLUGIN_GIT_TIMEOUT_MS | env-vars.md:77 | env-vars | RULE-CANDIDATE | Timeout in milliseconds for git operations when installing or updating plugins (default: 120000). Increase this... |
| 317 | CLAUDE_CODE_PLUGIN_SEED_DIR | env-vars.md:78 | env-vars | RULE-CANDIDATE | Path to one or more read-only plugin seed directories, separated by `:` on Unix or... |
| 318 | CLAUDE_CODE_PROXY_RESOLVES_HOSTS | env-vars.md:79 | env-vars | RULE-CANDIDATE | Set to `true` to allow the proxy to perform DNS resolution instead of the caller.... |
| 319 | CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS | env-vars.md:80 | env-vars | RULE-CANDIDATE | Maximum time in milliseconds for [SessionEnd](/en/hooks#sessionend) hooks to complete (default: `1500`). Applies to session exit,... |
| 320 | CLAUDE_CODE_SHELL | env-vars.md:81 | env-vars | RULE-CANDIDATE | Override automatic shell detection. Useful when your login shell differs from your preferred working shell... |
| 321 | CLAUDE_CODE_SHELL_PREFIX | env-vars.md:82 | env-vars | RULE-CANDIDATE | Command prefix to wrap all bash commands (for example, for logging or auditing). Example: `/path/to/logger.sh`... |
| 322 | CLAUDE_CODE_SIMPLE | env-vars.md:83 | env-vars | RULE-CANDIDATE | Set to `1` to run with a minimal system prompt and only the Bash, file... |
| 323 | CLAUDE_CODE_SKIP_BEDROCK_AUTH | env-vars.md:84 | env-vars | RULE-CANDIDATE | Skip AWS authentication for Bedrock (for example, when using an LLM gateway) |
| 324 | CLAUDE_CODE_SKIP_FAST_MODE_NETWORK_ERRORS | env-vars.md:85 | env-vars | RULE-CANDIDATE | Set to `1` to allow [fast mode](/en/fast-mode) when the organization status check fails due to... |
| 325 | CLAUDE_CODE_SKIP_FOUNDRY_AUTH | env-vars.md:86 | env-vars | RULE-CANDIDATE | Skip Azure authentication for Microsoft Foundry (for example, when using an LLM gateway) |
| 326 | CLAUDE_CODE_SKIP_VERTEX_AUTH | env-vars.md:87 | env-vars | RULE-CANDIDATE | Skip Google authentication for Vertex (for example, when using an LLM gateway) |
| 327 | CLAUDE_CODE_SUBAGENT_MODEL | env-vars.md:88 | env-vars | RULE-CANDIDATE | See [Model configuration](/en/model-config) |
| 328 | CLAUDE_CODE_SUBPROCESS_ENV_SCRUB | env-vars.md:89 | env-vars | RULE-CANDIDATE | Set to `1` to strip Anthropic and cloud provider credentials from subprocess environments (Bash tool,... |
| 329 | CLAUDE_CODE_TASK_LIST_ID | env-vars.md:90 | env-vars | RULE-CANDIDATE | Share a task list across sessions. Set the same ID in multiple Claude Code instances... |
| 330 | CLAUDE_CODE_TEAM_NAME | env-vars.md:91 | env-vars | RULE-CANDIDATE | Name of the agent team this teammate belongs to. Set automatically on [agent team](/en/agent-teams) members |
| 331 | CLAUDE_CODE_TMPDIR | env-vars.md:92 | env-vars | RULE-CANDIDATE | Override the temp directory used for internal temp files. Claude Code appends `/claude/` to this... |
| 332 | CLAUDE_CODE_USER_EMAIL | env-vars.md:93 | env-vars | RULE-CANDIDATE | Email address for the authenticated user. Used by SDK callers to provide account information synchronously.... |
| 333 | CLAUDE_CODE_USE_BEDROCK | env-vars.md:94 | env-vars | RULE-CANDIDATE | Use [Bedrock](/en/amazon-bedrock) |
| 334 | CLAUDE_CODE_USE_FOUNDRY | env-vars.md:95 | env-vars | RULE-CANDIDATE | Use [Microsoft Foundry](/en/microsoft-foundry) |
| 335 | CLAUDE_CODE_USE_POWERSHELL_TOOL | env-vars.md:96 | env-vars | RULE-CANDIDATE | Set to `1` to enable the PowerShell tool on Windows (opt-in preview). When enabled, Claude... |
| 336 | CLAUDE_CODE_USE_VERTEX | env-vars.md:97 | env-vars | RULE-CANDIDATE | Use [Vertex](/en/google-vertex-ai) |
| 337 | CLAUDE_CONFIG_DIR | env-vars.md:98 | env-vars | RULE-CANDIDATE | Customize where Claude Code stores its configuration and data files |
| 338 | CLAUDE_ENV_FILE | env-vars.md:99 | env-vars | RULE-CANDIDATE | Path to a shell script that Claude Code sources before each Bash command. Use to... |
| 339 | DISABLE_AUTOUPDATER | env-vars.md:100 | env-vars | RULE-CANDIDATE | Set to `1` to disable automatic updates. |
| 340 | DISABLE_COST_WARNINGS | env-vars.md:101 | env-vars | RULE-CANDIDATE | Set to `1` to disable cost warning messages |
| 341 | DISABLE_ERROR_REPORTING | env-vars.md:102 | env-vars | RULE-CANDIDATE | Set to `1` to opt out of Sentry error reporting |
| 342 | DISABLE_FEEDBACK_COMMAND | env-vars.md:103 | env-vars | RULE-CANDIDATE | Set to `1` to disable the `/feedback` command. The older name `DISABLE_BUG_COMMAND` is also accepted |
| 343 | DISABLE_INSTALLATION_CHECKS | env-vars.md:104 | env-vars | RULE-CANDIDATE | Set to `1` to disable installation warnings. Use only when manually managing the installation location,... |
| 344 | DISABLE_PROMPT_CACHING | env-vars.md:105 | env-vars | RULE-CANDIDATE | Set to `1` to disable prompt caching for all models (takes precedence over per-model settings) |
| 345 | DISABLE_PROMPT_CACHING_HAIKU | env-vars.md:106 | env-vars | RULE-CANDIDATE | Set to `1` to disable prompt caching for Haiku models |
| 346 | DISABLE_PROMPT_CACHING_OPUS | env-vars.md:107 | env-vars | RULE-CANDIDATE | Set to `1` to disable prompt caching for Opus models |
| 347 | DISABLE_PROMPT_CACHING_SONNET | env-vars.md:108 | env-vars | RULE-CANDIDATE | Set to `1` to disable prompt caching for Sonnet models |
| 348 | DISABLE_TELEMETRY | env-vars.md:109 | env-vars | RULE-CANDIDATE | Set to `1` to opt out of Statsig telemetry (note that Statsig events do not... |
| 349 | ENABLE_CLAUDEAI_MCP_SERVERS | env-vars.md:110 | env-vars | RULE-CANDIDATE | Set to `false` to disable [claude.ai MCP servers](/en/mcp#use-mcp-servers-from-claudeai) in Claude Code. Enabled by default for... |
| 350 | ENABLE_TOOL_SEARCH | env-vars.md:111 | env-vars | RULE-CANDIDATE | Controls [MCP tool search](/en/mcp#scale-with-mcp-tool-search). Unset: enabled by default, but disabled when `ANTHROPIC_BASE_URL` points to a... |
| 351 | FORCE_AUTOUPDATE_PLUGINS | env-vars.md:112 | env-vars | RULE-CANDIDATE | Set to `true` to force plugin auto-updates even when the main auto-updater is disabled via... |
| 352 | HTTP_PROXY | env-vars.md:113 | env-vars | RULE-CANDIDATE | Specify HTTP proxy server for network connections |
| 353 | HTTPS_PROXY | env-vars.md:114 | env-vars | RULE-CANDIDATE | Specify HTTPS proxy server for network connections |
| 354 | IS_DEMO | env-vars.md:115 | env-vars | RULE-CANDIDATE | Set to `true` to enable demo mode: hides email and organization from the UI, skips... |
| 355 | MAX_MCP_OUTPUT_TOKENS | env-vars.md:116 | env-vars | RULE-CANDIDATE | Maximum number of tokens allowed in MCP tool responses. Claude Code displays a warning when... |
| 356 | MAX_THINKING_TOKENS | env-vars.md:117 | env-vars | RULE-CANDIDATE | Override the [extended thinking](https://platform.claude.com/docs/en/build-with-claude/extended-thinking) token budget. The ceiling is the model's [max output tokens](https://platform.claude.com/docs/en/about-claude/models/overview#latest-models-comparison) minus... |
| 357 | MCP_CLIENT_SECRET | env-vars.md:118 | env-vars | RULE-CANDIDATE | OAuth client secret for MCP servers that require [pre-configured credentials](/en/mcp#use-pre-configured-oauth-credentials). Avoids the interactive prompt when... |
| 358 | MCP_OAUTH_CALLBACK_PORT | env-vars.md:119 | env-vars | RULE-CANDIDATE | Fixed port for the OAuth redirect callback, as an alternative to `--callback-port` when adding an... |
| 359 | MCP_TIMEOUT | env-vars.md:120 | env-vars | RULE-CANDIDATE | Timeout in milliseconds for MCP server startup |
| 360 | MCP_TOOL_TIMEOUT | env-vars.md:121 | env-vars | RULE-CANDIDATE | Timeout in milliseconds for MCP tool execution |
| 361 | NO_PROXY | env-vars.md:122 | env-vars | RULE-CANDIDATE | List of domains and IPs to which requests will be directly issued, bypassing proxy |
| 362 | SLASH_COMMAND_TOOL_CHAR_BUDGET | env-vars.md:123 | env-vars | RULE-CANDIDATE | Override the character budget for skill metadata shown to the [Skill tool](/en/skills#control-who-invokes-a-skill). The budget scales... |
| 363 | USE_BUILTIN_RIPGREP | env-vars.md:124 | env-vars | RULE-CANDIDATE | Set to `0` to use system-installed `rg` instead of `rg` included with Claude Code |
| 364 | VERTEX_REGION_CLAUDE_3_5_HAIKU | env-vars.md:125 | env-vars | RULE-CANDIDATE | Override region for Claude 3.5 Haiku when using Vertex AI |
| 365 | VERTEX_REGION_CLAUDE_3_7_SONNET | env-vars.md:126 | env-vars | RULE-CANDIDATE | Override region for Claude 3.7 Sonnet when using Vertex AI |
| 366 | VERTEX_REGION_CLAUDE_4_0_OPUS | env-vars.md:127 | env-vars | RULE-CANDIDATE | Override region for Claude 4.0 Opus when using Vertex AI |
| 367 | VERTEX_REGION_CLAUDE_4_0_SONNET | env-vars.md:128 | env-vars | RULE-CANDIDATE | Override region for Claude 4.0 Sonnet when using Vertex AI |
| 368 | VERTEX_REGION_CLAUDE_4_1_OPUS | env-vars.md:129 | env-vars | RULE-CANDIDATE | Override region for Claude 4.1 Opus when using Vertex AI |

## Evaluation Prompt

@harness-author: Evaluate each finding above using the taxonomy decision tree
and earned-prose filters from your SKILL.md.

For each *-CANDIDATE: produce an implementation sketch (target file, estimated
token cost, which earned-prose test it passes, recommended artifact type).

For each SUPERSEDES: produce a review of the superseded artifact in standard
review format (Verdict / Findings table / Token Impact).

For each NEEDS-REVIEW: make a final disposition using the full taxonomy tree.

Write output to plans/harness-evo-eval.md. Commit to current branch. Create PR
against claude-specific-harnessing with a title and body that summarizes the
findings evaluated and verdicts reached.
