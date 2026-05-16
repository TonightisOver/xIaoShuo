# Gate 1: Block stage 3+ files until user approves stage 2 tech design
# Triggers on: Write/Edit to .harness/changes/CHANGE-*/03-* or 04-*

$input_json = [Console]::In.ReadToEnd() | ConvertFrom-Json
$file_path = $input_json.tool_input.file_path

if (-not $file_path) { exit 0 }

# Only check files inside harness changes directories
if ($file_path -notmatch '\.harness[/\\]changes[/\\](CHANGE-[^/\\]+)[/\\](03|04)-') {
    exit 0
}

$change_dir = [System.IO.Path]::GetDirectoryName($file_path)

# Check 02-tech-design exists
$design_file = Join-Path $change_dir "02-技术设计.md"
if (-not (Test-Path $design_file)) {
    [Console]::Error.WriteLine("[Gate 1 BLOCKED] Tech design not found: $design_file - complete stage 2 first.")
    exit 2
}

# Check user approval marker
$approval_file = Join-Path $change_dir ".gate1-approved"
if (-not (Test-Path $approval_file)) {
    [Console]::Error.WriteLine("[Gate 1 BLOCKED] Tech design not yet approved by user. After confirming the architecture, create: $approval_file")
    exit 2
}

exit 0
