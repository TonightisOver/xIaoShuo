# Gate 2: Block summary.md "completed" status until stage 10 deploy report exists
# Triggers on: Write/Edit to .harness/changes/CHANGE-*/summary.md

$input_json = [Console]::In.ReadToEnd() | ConvertFrom-Json
$file_path = $input_json.tool_input.file_path
$content = $input_json.tool_input.content

if (-not $file_path) { exit 0 }

# Only check summary.md inside harness changes directories
if ($file_path -notmatch '\.harness[/\\]changes[/\\]CHANGE-[^/\\]+[/\\]summary\.md$') {
    exit 0
}

# Only block when marking as completed (check for Unicode codepoints of 已完成)
# U+5DF2 U+5B8C U+6210
$completed = [char]0x5DF2 + [char]0x5B8C + [char]0x6210
if ($content -notmatch $completed) {
    exit 0
}

$change_dir = [System.IO.Path]::GetDirectoryName($file_path)

# Check deploy verification report exists (any version)
# Filename starts with: 10- followed by Unicode for 部署验证报告
$deploy_reports = Get-ChildItem -Path $change_dir -Filter "10-*.md" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^10-' }
if (-not $deploy_reports) {
    [Console]::Error.WriteLine("[Gate 2 BLOCKED] No deploy verification report found (10-*.md). Complete stage 10 before closing the change.")
    exit 2
}

exit 0
