# Set environment variables and run readiness check
$env:DHAN_CLIENT_ID = "1101936133"
$env:DHAN_ACCESS_TOKEN = "test_token_for_readiness_check"

Write-Host "Environment variables set:"
Write-Host "DHAN_CLIENT_ID = $env:DHAN_CLIENT_ID"
Write-Host "DHAN_ACCESS_TOKEN = $env:DHAN_ACCESS_TOKEN"

Write-Host "`nRunning readiness check..."
python run_readiness_check.py
