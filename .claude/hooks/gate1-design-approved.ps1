# Gate 1: Block stage 3+ implementation files until design is approved
# Approval marker: .gate1-approved file in the change directory

$input_json = [Console]::In.ReadToEnd() | ConvertFrom-Json
$file_path = $input_json.tool_input.file_path

if (-not $file_path) { exit 0 }

# Only check harness change directories
if ($file_path -notmatch 'harness\changes\CHANGE-\d{3}-') {
    exit 0
}

# Only block stage 3+ files (03-coding plan, 04-implementation, and beyond)
if ($file_path -notmatch '(03|04|05|06|07|08|09|10)-') {
    exit 0
}

# Extract change directory
$change_dir = [System.IO.Path]::GetDirectoryName($file_path)
if (-not [System.IO.Path]::IsPathRooted($change_dir)) {
    $change_dir = Join-Path (Get-Location) $change_dir
}

$approval_file = Join-Path $change_dir '.gate1-approved'
if (-not (Test-Path $approval_file)) {
    [Console]::Error.WriteLine("[Gate 1 BLOCKED] Design not yet approved. After reviewing the tech design (02-*.md), create the approval marker at: $approval_file")
    [Console]::Error.WriteLine("[Gate 1] To approve: New-Item -Path '$approval_file' -ItemType File")
    exit 2
}

exit 0
