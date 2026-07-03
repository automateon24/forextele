@echo off
echo ====================================
echo 🧪 COMPREHENSIVE TESTING FRAMEWORK
echo ====================================
echo 🔍 Sanity Tests | Security Tests | Unit Tests | Functional Tests
echo 🛡️ Critical Issue Coverage | Bug Detection | Quality Assurance
echo ====================================

echo.
echo 🚀 Starting comprehensive testing...
echo 📅 %date% %time%
echo.

cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel neq 0 (
    echo ❌ Python not found. Please install Python first.
    pause
    exit /b 1
)

REM Check if we're in the right directory
if not exist "run_tests.py" (
    echo ❌ run_tests.py not found. Please run from TEST_FRAMEWORK directory.
    pause
    exit /b 1
)

REM Check for command line arguments
set TEST_MODE=standard
if "%1"=="" goto :run_tests
if "%1"=="quick" set TEST_MODE=quick
if "%1"=="standard" set TEST_MODE=standard
if "%1"=="comprehensive" set TEST_MODE=comprehensive
if "%1"=="production" set TEST_MODE=production

:run_tests
echo 🎯 Test Mode: %TEST_MODE%
echo.

REM Run the tests
python run_tests.py %TEST_MODE%

REM Check results
if errorlevel neq 0 (
    echo.
    echo ❌ Tests failed! Check the report for details.
    echo.
    echo 🔍 Open TEST_REPORTS directory to see detailed results.
    explorer TEST_REPORTS
) else (
    echo.
    echo ✅ All tests passed! System is ready.
    echo.
    echo 📊 Check TEST_REPORTS directory for detailed results.
    explorer TEST_REPORTS
)

echo.
echo 🏁 Testing completed!
pause
