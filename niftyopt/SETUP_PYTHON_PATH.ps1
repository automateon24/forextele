# SETUP_PYTHON_PATH.ps1
# Finds and configures Python path for all trading scripts
# Run this ONCE to fix Python path issues permanently

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Python Path Setup for Trading System" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Search paths for Python
$SearchPaths = @(
    "c:\Python314\python.exe",
    "c:\cursor\options\niftyopt\venv\Scripts\python.exe",
    "c:\cursor\options\niftyopt\trading_env\Scripts\python.exe",
    "c:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python314\python.exe",
    "c:\Program Files\Python314\python.exe"
)

$PythonPath = $null
$FoundPython = $false

# Check each path
Write-Host "Searching for Python..." -ForegroundColor Yellow
foreach ($path in $SearchPaths) {
    if (Test-Path $path) {
        Write-Host "  Found: $path" -ForegroundColor Green
        $PythonPath = $path
        $FoundPython = $true
        break
    } else {
        Write-Host "  Not found: $path" -ForegroundColor Gray
    }
}

# If not found in common paths, search more broadly
if (-not $FoundPython) {
    Write-Host "Searching in project directory..." -ForegroundColor Yellow
    $VenvPython = Get-ChildItem -Path "c:\cursor\options\niftyopt" -Recurse -Filter "python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($VenvPython) {
        $PythonPath = $VenvPython.FullName
        $FoundPython = $true
        Write-Host "  Found: $PythonPath" -ForegroundColor Green
    }
}

if (-not $FoundPython) {
    Write-Host "ERROR: Python not found!" -ForegroundColor Red
    Write-Host "Please install Python or provide the path manually." -ForegroundColor Red
    exit 1
}

# Test Python works
Write-Host ""
Write-Host "Testing Python..." -ForegroundColor Yellow
try {
    $Version = & $PythonPath --version 2>&1
    Write-Host "  Python version: $Version" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python exists but cannot execute!" -ForegroundColor Red
    exit 1
}

# Save configuration
$ConfigFile = "c:\cursor\options\niftyopt\python_config.txt"
$PythonPath | Out-File -FilePath $ConfigFile -Encoding ASCII
Write-Host ""
Write-Host "Python path saved to: $ConfigFile" -ForegroundColor Green
Write-Host "Path: $PythonPath" -ForegroundColor Cyan

# Create a validation script
$ValidateScript = @"
@echo off
rem VALIDATE_PYTHON.bat
rem Checks Python is available before running trading scripts

set "CONFIG_FILE=c:\cursor\options\niftyopt\python_config.txt"
set "PYTHON_PATH="

if not exist "%CONFIG_FILE%" (
    echo ERROR: Python configuration not found!
    echo Run: SETUP_PYTHON_PATH.ps1 first
    exit /b 1
)

for /f "delims=" %%i in (%CONFIG_FILE%) do set "PYTHON_PATH=%%i"

if not exist "%PYTHON_PATH%" (
    echo ERROR: Python not found at: %PYTHON_PATH%
    echo Run: SETUP_PYTHON_PATH.ps1 to reconfigure
    exit /b 1
)

rem Test Python works
"%PYTHON_PATH%" --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python exists but cannot execute!
    echo Path: %PYTHON_PATH%
    exit /b 1
)

exit /b 0
"@

$ValidateScript | Out-File -FilePath "c:\cursor\options\niftyopt\VALIDATE_PYTHON.bat" -Encoding ASCII

# Create wrapper batch generator
$WrapperTemplate = @"
@echo off
rem AUTO-GENERATED BATCH FILE
rem Uses Python from: {PYTHON_PATH}

set "PYTHON_EXE={PYTHON_PATH}"

rem Validate Python first
call c:\cursor\options\niftyopt\VALIDATE_PYTHON.bat
if errorlevel 1 (
    echo.
    echo ============================================
    echo PYTHON VALIDATION FAILED
    echo Run: SETUP_PYTHON_PATH.ps1
    echo ============================================
    pause
    exit /b 1
)

rem Run the script
cd /d "c:\cursor\options\niftyopt"
"%PYTHON_EXE%" %1 %2 %3
"@

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "SETUP COMPLETE!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Files created:" -ForegroundColor Cyan
Write-Host "  - python_config.txt (Python path)" -ForegroundColor White
Write-Host "  - VALIDATE_PYTHON.bat (validation script)" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Run trading scripts - they will auto-find Python" -ForegroundColor White
Write-Host "  2. If Python moves, run this script again" -ForegroundColor White
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
