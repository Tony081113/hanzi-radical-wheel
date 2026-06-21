# 啟動本機遊戲與受保護的題庫更新服務。
$env:CRAWL_AUTH_TOKEN = [System.Guid]::NewGuid().ToString('N')
Write-Host "本次題庫更新密鑰（請貼到遊戲頁）： $env:CRAWL_AUTH_TOKEN" -ForegroundColor Yellow
python "$PSScriptRoot\app.py"
