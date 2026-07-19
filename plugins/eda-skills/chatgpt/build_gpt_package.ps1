# Rebuild the ChatGPT Custom GPT knowledge package for the EDA skills.
# Run this after any change to eda_skills/*/references, */scripts, or SKILL.md.
# See chatgpt/README.md for the full install/update workflow.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot   # eda_skills/ (this script lives in eda_skills/chatgpt/)
$dist = Join-Path $root "dist"
New-Item -ItemType Directory -Force -Path $dist | Out-Null

$skillsRoot = Join-Path $root "skills"
if (-not (Test-Path $skillsRoot)) {
    $skillsRoot = $root
}

# 1. Clean bytecode caches so they don't bloat the archive.
Get-ChildItem -Path $root -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force

# 2. Stage exactly what the GPT needs: SKILL.md + references/ + scripts/ (+ assets/ for
#    plan-eda-dataset) per skill, and the root requirements.txt. Excluded on purpose:
#    agents/openai.yaml (a different distribution format, not used by Custom GPT),
#    README*.md, tests/, dist/, chatgpt/ itself.
$stage = Join-Path $env:TEMP "eda_skills_knowledge_stage"
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

$skills = "plan-eda-dataset", "audit-eda-data-quality", "discover-eda-structure", "engineer-select-eda-features"
foreach ($s in $skills) {
    $srcSkill = Join-Path $skillsRoot $s
    if (-not (Test-Path $srcSkill)) { throw "Missing skill directory: $srcSkill" }
    $dstSkill = Join-Path $stage $s
    New-Item -ItemType Directory -Force -Path $dstSkill | Out-Null
    Copy-Item (Join-Path $srcSkill "SKILL.md") $dstSkill
    foreach ($sub in "references", "scripts", "assets") {
        $srcSub = Join-Path $srcSkill $sub
        if (Test-Path $srcSub) {
            Copy-Item $srcSub $dstSkill -Recurse
        }
    }
    Get-ChildItem -Path $dstSkill -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force
}
Copy-Item (Join-Path $root "requirements.txt") $stage

# 3. Zip it.
$knowledgeZip = Join-Path $dist "eda_skills_knowledge.zip"
if (Test-Path $knowledgeZip) { Remove-Item -LiteralPath $knowledgeZip -Force }
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $knowledgeZip -Force
Remove-Item -Recurse -Force $stage

# 4. Report.
$zipInfo = Get-Item $knowledgeZip
Write-Output ("Knowledge zip: {0} ({1:N0} bytes)" -f $zipInfo.Name, $zipInfo.Length)

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
Write-Output "  2) Enable capability 'Code Interpreter & Data Analysis'"
Write-Output "  3) Upload $knowledgeZip under 'Knowledge'"
Write-Output "Full guide: chatgpt/README.md"
