# CLAUDE_CODE_AUTO_COMPACT_WINDOW: Compaction Threshold Awareness

> Auto-compaction fires when the running token count crosses this threshold. The default is the model's full context size -- meaning compaction may arrive later than workflow state requires.

## Cost Model

Window sizing is a tradeoff: too high risks context overflow and abrupt truncation, too low discards context downstream steps may still need.

## [HARD] Implication for Sub-Agent Isolation

When authoring multi-agent workflows, do not assume a sub-agent launched mid-session inherits clean context. If `CLAUDE_CODE_AUTO_COMPACT_WINDOW` is at or near the default, a parent agent that has consumed significant tokens may compact before launching sub-agents -- compressing the state the sub-agent depends on.

Design sub-agents to receive their required context explicitly (task files, manifest paths) rather than relying on inherited session state.

## Reference

- Env var: `CLAUDE_CODE_AUTO_COMPACT_WINDOW`
- Default: model's full context window size (model-dependent)
- Scope: affects all Claude Code sessions in the environment
