# NAVIGATION PROTOCOL: Read Surgically, Not Speculatively

Every file read costs context window tokens -- the scarcest resource in a session. Before reading any file, know what specific information you need.

## Failure Modes to Avoid

1. **The "Lazy Dump"**: Reading an entire large file when only one function or section was needed. Narrows nothing, wastes tokens.
2. **The "Grep Spam"**: Running repeated broad searches instead of refining the pattern or path. Each redundant search multiplies token cost with no new signal.
3. **The "Name Grep"**: Using a content search tool to find a file by name -- it scans file *contents*, not filenames, and will scan the entire repo unnecessarily.
4. **The "Symbol Grep"**: Using grep to find Python symbol references -- it won't distinguish comments, strings, or partial name collisions from real usages, producing false positives that require more reads to resolve.
