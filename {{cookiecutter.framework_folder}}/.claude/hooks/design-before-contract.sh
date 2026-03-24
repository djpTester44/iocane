#!/usr/bin/env bash
# PreToolUse hook: Edit | Write
# Blocks writing interfaces/*.pyi files unless a matching CRC card exists
# in plans/project-spec.md for the Protocol name derived from the filename.
# Skip if .iocane/validating sentinel exists (automated spec validation workflows).

# Skip during automated validation
if [ -f ".iocane/validating" ]; then
    exit 0
fi

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | uv run python -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
")

# Check if the target is an interfaces/*.pyi file
IS_INTERFACE=$(FILE_PATH="$FILE_PATH" uv run python -c "
import os, sys
p = os.path.normpath(os.environ['FILE_PATH']).replace('\\\\', '/')
parts = p.split('/')
# Match if 'interfaces' directory contains a .pyi file
if len(parts) >= 2 and parts[-2] == 'interfaces' and parts[-1].endswith('.pyi'):
    print('yes')
else:
    print('no')
")

if [ "$IS_INTERFACE" != "yes" ]; then
    exit 0
fi

# Derive PascalCase component name from filename
COMPONENT_NAME=$(FILE_PATH="$FILE_PATH" uv run python -c "
import os, re, sys
path = os.environ['FILE_PATH']
basename = os.path.basename(path)
stem = os.path.splitext(basename)[0]  # remove .pyi
# Convert snake_case to PascalCase
parts = stem.split('_')
pascal = ''.join(p.capitalize() for p in parts if p)
print(pascal)
")

if [ -z "$COMPONENT_NAME" ]; then
    exit 0
fi

# Check if project-spec.md exists
if [ ! -f "plans/project-spec.md" ]; then
    echo "BLOCKED: plans/project-spec.md does not exist. Run /io-architect to design components before writing contracts."
    exit 2
fi

# Search for a CRC card matching the component name
FOUND=$(COMPONENT_NAME="$COMPONENT_NAME" uv run python -c "
import re, sys, os
component = os.environ['COMPONENT_NAME']
try:
    content = open('plans/project-spec.md', encoding='utf-8').read()
    pattern = re.compile(
        r'###\s+' + re.escape(component) +
        r'|\*\*Component:\*\*\s*' + re.escape(component),
        re.MULTILINE
    )
    print('yes' if pattern.search(content) else 'no')
except Exception:
    print('no')
")

if [ "$FOUND" != "yes" ]; then
    echo "BLOCKED: No CRC card for $COMPONENT_NAME in plans/project-spec.md. Design the component before writing the contract."
    exit 2
fi

exit 0
