#!/bin/bash
# Gate 1: Block stage 3+ implementation files until design is approved
# Approval marker: .gate1-approved file in the change directory

INPUT_JSON=$(cat)

FILE_PATH=$(python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('file_path', ''))
except:
    pass
" <<< "$INPUT_JSON")

if [ -z "$FILE_PATH" ]; then
    echo "{}"
    exit 0
fi

# Only check harness change directories
if [[ ! "$FILE_PATH" =~ harness/changes/CHANGE-[0-9]{3}- ]]; then
    echo "{}"
    exit 0
fi

# Only block stage 3+ files
if [[ ! "$FILE_PATH" =~ /(03|04|05|06|07|08|09|10)- ]]; then
    echo "{}"
    exit 0
fi

CHANGE_DIR=$(dirname "$FILE_PATH")
if [[ "$CHANGE_DIR" != /* ]]; then
    CHANGE_DIR="$PWD/$CHANGE_DIR"
fi

APPROVAL_FILE="$CHANGE_DIR/.gate1-approved"
if [ ! -f "$APPROVAL_FILE" ]; then
    echo "[Gate 1 BLOCKED] Design not yet approved. After reviewing the tech design (02-*.md), create the approval marker at: $APPROVAL_FILE" >&2
    echo "[Gate 1] To approve: touch '$APPROVAL_FILE'" >&2
    # Ensure stdout is valid JSON even on failure
    echo '{}'
    exit 1
fi

echo "{}"
exit 0
