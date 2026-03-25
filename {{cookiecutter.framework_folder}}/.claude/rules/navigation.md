# NAVIGATION PROTOCOL: Read Surgically, Not Speculatively

Every file read costs context window tokens -- the scarcest resource in a session. Before reading any file, know what specific information you need.

## Failure Modes to Avoid

1. **The "Lazy Dump"**: Reading an entire large file when only one function or section was needed. Narrows nothing, wastes tokens.
2. **The "Grep Spam"**: Running repeated broad searches instead of refining the pattern or path. Each redundant search multiplies token cost with no new signal.
3. **The "Name Grep"**: Using a content search tool to find a file by name -- it scans file *contents*, not filenames, wasting a full-repo scan on what a filename lookup solves instantly.
4. **The "Symbol Grep"**: Using grep to find Python symbol references -- it can't distinguish real usages from comments or partial collisions, multiplying reads to resolve false positives.
