# Gate 1: Block stage 3+ files until user approves stage 2 tech design

$input_json = [Console]::In.ReadToEnd() | ConvertFrom-Json
$file_path = $input_json.tool_input.file_path

if (-not $file_path) { exit 0 }

if ($file_path -notmatch 'harness.changes.CHANGE-.+.(03|04)-') {
    exit 0
}

$change_dir = [System.IO.Path]::GetDirectoryName($file_path)
if (-not [System.IO.Path]::IsPathRooted($change_dir)) {
    $change_dir = Join-Path (Get-Location) $change_dir
}

$design_files = Get-ChildItem -Path $change_dir -Filter "02-*.md" -ErrorAction SilentlyContinue
if (-not $design_files) {
    [Console]::Error.WriteLine("[Gate 1 BLOCKED] Tech design (02-*.md) not found in $change_dir - complete stage 2 first.")
    exit 2
}

$approval_file = Join-Path $change_dir ".gate1-approved"
if (-not (Test-Path $approval_file)) {
    [Console]::Error.WriteLine("[Gate 1 BLOCKED] Tech design not yet approved. After confirming the architecture, create: $approval_file")
    exit 2
}

exit 0
