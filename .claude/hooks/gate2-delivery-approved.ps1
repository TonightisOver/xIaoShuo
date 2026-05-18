# Gate 2: Block summary.md "completed" status until deploy verification exists
# Deploy report: 10-*.md must exist in the change directory

$input_json = [Console]::In.ReadToEnd() | ConvertFrom-Json
$file_path = $input_json.tool_input.file_path
$content = $input_json.tool_input.content

if (-not $file_path) { exit 0 }

# Only check summary.md in harness change directories
if ($file_path -notmatch 'harness\changes\CHANGE-\d{3}-.*summary\.md$') {
    exit 0
}

# Only block when content contains "已完成"
if (-not $content -or $content -notmatch '已完成') {
    exit 0
}

# Extract change directory
$change_dir = [System.IO.Path]::GetDirectoryName($file_path)
if (-not [System.IO.Path]::IsPathRooted($change_dir)) {
    $change_dir = Join-Path (Get-Location) $change_dir
}

$deploy_reports = Get-ChildItem -Path $change_dir -Filter '10-*.md' -ErrorAction SilentlyContinue
if (-not $deploy_reports) {
    [Console]::Error.WriteLine("[Gate 2 BLOCKED] No deploy verification report (10-*.md) found in $change_dir")
    [Console]::Error.WriteLine("[Gate 2] Complete stage 10 (deploy verification) before marking the change as completed.")
    exit 2
}

exit 0
