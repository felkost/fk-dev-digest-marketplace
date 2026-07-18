# Перезбирає Knowledge-пакет Custom GPT для ml-advisor скілів.
# Запускати після будь-якої зміни в */SKILL.md, */references, */scripts.
# Повна інструкція встановлення/оновлення: chatgpt/README.md.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot   # agent_ml_interviewer/ (скрипт лежить у chatgpt/)
$dist = Join-Path $root "dist"
New-Item -ItemType Directory -Force -Path $dist | Out-Null

$skills = "ml-metric-choice", "ml-decision-threshold", "ml-distribution-choice",
          "ml-overfitting-diagnosis", "ml-search-strategy",
          "ml-tree-ensemble-params", "ml-linear-regularization",
          "ml-clustering-k", "ml-dimensionality-features",
          "rl-hyperparameters", "llm-parameter-choice", "ml-tuning-workflow",
          "ml-task-framing", "ml-model-selection", "ml-validation-design",
          "nn-training-params", "ml-bayesian-inference", "ml-missing-data",
          "ml-sampling-design", "ml-label-quality", "ml-forecasting-model"

# 1. Прибрати кеші байткоду, щоб не роздували архів.
Get-ChildItem -Path $root -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force

# 2. Стейджити рівно те, що потрібно GPT: SKILL.md + references/ + scripts/ на скіл
#    + кореневий requirements.txt. Свідомо ВИКЛЮЧЕНО: agents/openai.yaml (інший
#    формат дистрибуції), README*, tests/, dist/, evals/, .claude/, chatgpt/.
$stage = Join-Path $env:TEMP "ml_advisor_knowledge_stage"
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force -Path $stage | Out-Null

foreach ($s in $skills) {
    $src = Join-Path $root $s
    $dst = Join-Path $stage $s
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    Copy-Item (Join-Path $src "SKILL.md") $dst
    foreach ($sub in "references", "scripts", "assets") {
        $p = Join-Path $src $sub
        if (Test-Path $p) { Copy-Item $p $dst -Recurse }
    }
}
Copy-Item (Join-Path $root "requirements.txt") $stage

# 3. Knowledge-архів + по одному zip на скіл (для окремого розповсюдження).
$knowledgeZip = Join-Path $dist "ml_advisor_knowledge.zip"
if (Test-Path $knowledgeZip) { Remove-Item -LiteralPath $knowledgeZip -Force }
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $knowledgeZip -Force

foreach ($s in $skills) {
    $zip = Join-Path $dist "$s.zip"
    if (Test-Path $zip) { Remove-Item -LiteralPath $zip -Force }
    Compress-Archive -Path (Join-Path $stage $s) -DestinationPath $zip -Force
}
Remove-Item -Recurse -Force $stage

$zipInfo = Get-Item $knowledgeZip
Write-Output ("Knowledge zip: {0} ({1:N0} bytes)" -f $zipInfo.Name, $zipInfo.Length)

# 4. Ліміт Instructions у ChatGPT — 8000 БАЙТІВ UTF-8, не символів:
#    кирилиця — 2 байти/літера, тому міряємо байти.
$instrPath  = Join-Path $PSScriptRoot "gpt_instructions.md"
$instrText  = Get-Content -Raw -Encoding UTF8 $instrPath
$instrBytes = [System.Text.Encoding]::UTF8.GetByteCount($instrText)
$budget = 8000
Write-Output ("Instructions: {0} UTF-8 bytes / {1} chars (ліміт {2}; живий ліміт звіряйте в редакторі GPT)" -f `
    $instrBytes, $instrText.Length, $budget)
if ($instrBytes -gt $budget) {
    Write-Warning "Instructions перевищують байтовий бюджет — скоротіть перед вставкою."
} else {
    Write-Output "OK — у межах бюджету."
}

Write-Output ""
Write-Output "Далі в ChatGPT -> Explore GPTs -> Create -> Configure:"
Write-Output "  1) Вставити gpt_instructions.md у поле Instructions"
Write-Output "  2) Увімкнути capability 'Code Interpreter & Data Analysis'"
Write-Output "  3) Завантажити $knowledgeZip у Knowledge"
Write-Output "Повний гайд: chatgpt/README.md"
