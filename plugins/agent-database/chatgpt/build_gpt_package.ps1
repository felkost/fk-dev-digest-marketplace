# Rebuild the ChatGPT Custom GPT knowledge package for the agent-database skills.
# Run this after any change to skills/*/SKILL.md or skills/*/references.
# See chatgpt/README.md for the full install/update workflow.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot   # agent-database/ (this script lives in agent-database/chatgpt/)
$dist = Join-Path $root "dist"
New-Item -ItemType Directory -Force -Path $dist | Out-Null

$skillsRoot = Join-Path $root "skills"
if (-not (Test-Path $skillsRoot)) {
    $skillsRoot = $root
}

# 1. Stage exactly what the GPT needs: SKILL.md + references/ per skill. Excluded on purpose:
#    the plugin-level agents/, README.md, HANDOFF.md, CLAUDE.md, dist/, chatgpt/ itself.
$stage = Join-Path $env:TEMP "agent_database_knowledge_stage"
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

$skills = "analyze-task-conditions", "analyze-sql-examples", "explain-sqlite-mongodb",
          "db-connectivity-cloud", "build-data-projects", "design-dwh-etl", "bi-analytics"
foreach ($s in $skills) {
    $srcSkill = Join-Path $skillsRoot $s
    if (-not (Test-Path $srcSkill)) { throw "Missing skill directory: $srcSkill" }
    $dstSkill = Join-Path $stage $s
    New-Item -ItemType Directory -Force -Path $dstSkill | Out-Null
    Copy-Item (Join-Path $srcSkill "SKILL.md") $dstSkill
    $refs = Join-Path $srcSkill "references"
    if (Test-Path $refs) { Copy-Item $refs $dstSkill -Recurse }
}

# 2. Zip it.
$knowledgeZip = Join-Path $dist "agent_database_knowledge.zip"
if (Test-Path $knowledgeZip) { Remove-Item -LiteralPath $knowledgeZip -Force }
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $knowledgeZip -Force
Remove-Item -Recurse -Force $stage

# 3. Report.
$zipInfo = Get-Item $knowledgeZip
$fileCount = (Get-ChildItem -Path $root\skills -Recurse -Filter "*.md" | Measure-Object).Count
Write-Output ("Knowledge zip: {0} ({1:N0} bytes, {2} markdown files staged)" -f $zipInfo.Name, $zipInfo.Length, $fileCount)

# ChatGPT's 8000 limit is enforced on UTF-8 BYTES, not characters: Cyrillic is
# 2 bytes/letter, so a 5.5k-char Ukrainian text can still be rejected. Check bytes.
$instrPath = Join-Path $PSScriptRoot "gpt_instructions.md"
$instrText = Get-Content -Raw -Encoding UTF8 $instrPath
$instrChars = $instrText.Length
$instrBytes = [System.Text.Encoding]::UTF8.GetByteCount($instrText)
$budget = 8000
Write-Output ("Instructions length: {0} UTF-8 bytes / {1} chars (limit {2} bytes; verify the live limit in ChatGPT's GPT editor, it can change)" -f $instrBytes, $instrChars, $budget)
if ($instrBytes -gt $budget) {
    Write-Warning "Instructions exceed the byte budget -- trim before pasting into ChatGPT."
} else {
    Write-Output "OK - within budget."
}

Write-Output ""
Write-Output "Next steps in ChatGPT -> Explore GPTs -> Create -> Configure:"
Write-Output "  1) Paste gpt_instructions.md into 'Instructions'"
Write-Output "  2) Enable capability 'Code Interpreter & Data Analysis' (required) and 'Web Browsing' (recommended)"
Write-Output "  3) Upload $knowledgeZip under 'Knowledge'"
Write-Output "Full guide: chatgpt/README.md"
