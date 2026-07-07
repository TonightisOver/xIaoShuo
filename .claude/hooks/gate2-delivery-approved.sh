#!/bin/bash
# Gate 2: Block summary.md "completed" status until deploy verification exists
# Deploy report: 10-*.md must exist in the change directory

INPUT_JSON=$(cat)

FILE_PATH=$(python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('file_path', ''))
except:
    pass
" <<< "$INPUT_JSON")

CONTENT=$(python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('content', ''))
except:
    pass
" <<< "$INPUT_JSON")

if [ -z "$FILE_PATH" ]; then
    echo "{}"
    exit 0
fi

# Only check summary.md in harness change directories
if [[ ! "$FILE_PATH" =~ harness/changes/CHANGE-[0-9]{3}-.*summary\.md$ ]]; then
    echo "{}"
    exit 0
fi

if [[ "$CONTENT" != *"已完成"* ]]; then
    echo "{}"
    exit 0
fi

CHANGE_DIR=$(dirname "$FILE_PATH")
if [[ "$CHANGE_DIR" != /* ]]; then
    CHANGE_DIR="$PWD/$CHANGE_DIR"
fi

# Check for deploy report 10-*.md
shopt -s nullglob
FILES=("$CHANGE_DIR"/10-*.md)
if [ ${#FILES[@]} -eq 0 ]; then
    echo "[Gate 2 BLOCKED] No deploy verification report (10-*.md) found in $CHANGE_DIR" >&2
    echo "[Gate 2] Complete stage 10 (deploy verification) before marking the change as completed." >&2
    echo '{"error": "Deploy report missing"}'
    exit 1
fi

echo "{}"
exit 0
