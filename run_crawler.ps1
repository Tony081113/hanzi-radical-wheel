# 互動式題庫建立器：在 PowerShell 執行 .\run_crawler.ps1
$count = Read-Host "要從教育部辭典建立幾題？（建議 20～100）"
if ($count -notmatch '^\d+$' -or [int]$count -lt 1) {
    Write-Host "請輸入大於 0 的整數。" -ForegroundColor Red
    exit 1
}

$scope = Read-Host "掃描多少個部首索引？直接按 Enter 使用 24；輸入 0 掃描全部（較久）"
if ([string]::IsNullOrWhiteSpace($scope)) { $scope = 24 }
if ($scope -notmatch '^\d+$') {
    Write-Host "請輸入 0 或正整數。" -ForegroundColor Red
    exit 1
}

$rare = Read-Host "接受生僻字嗎？（y/N）"
$arguments = @("$PSScriptRoot\scrape_dictionary.py", '--limit', $count, '--max-radicals', $scope)
if ($rare -match '^(y|yes|是)$') { $arguments += '--allow-rare' }

python @arguments
if ($LASTEXITCODE -eq 0) {
    Write-Host "題庫已更新：$PSScriptRoot\questions.json" -ForegroundColor Green
}
