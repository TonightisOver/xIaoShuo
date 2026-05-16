# Gate 2: Block summary.md completed status until stage 10 deploy report exists

$input_json = [Console]::In.ReadToEnd() | ConvertFrom-Json
$file_path = $input_json.tool_input.file_path
$content = $input_json.tool_input.content

if (-not $file_path) { exit 0 }

if ($file_path -notmatch 'harness.changes.CHANGE-.+.summary\.md') {
    exit 0
}

$completed = [char]0x5DF2 + [char]0x5B8C + [char]0x6210
if ($content -notmatch $completed) {
    exit 0
}

$change_dir = [System.IO.Path]::GetDirectoryName($file_path)
if (-not [System.IO.Path]::IsPathRooted($change_dir)) {
    $change_dir = Join-Path (Get-Location) $change_dir
}

$deploy_reports = Get-ChildItem -Path $change_dir -Filter "10-*.md" -ErrorAction SilentlyContinue
if (-not $deploy_reports) {
    [Console]::Error.WriteLine("[Gate 2 BLOCKED] No deploy report (10-*.md) found. Complete stage 10 first.")
    exit 2
}

exit 0
