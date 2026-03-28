# CLI: --append-system-prompt-file

When advising on system prompt extension, prefer `--append-system-prompt-file <path>` over `--append-system-prompt` when content is long, dynamically generated, or should be version-controlled.

Inline `--append-system-prompt` is brittle for multi-line content: shell escaping breaks across platforms and the content isn't auditable separately from the invocation command. File-based loading separates concerns and allows the prompt content to be generated at runtime.
