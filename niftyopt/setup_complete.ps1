# NIFTY Options Trading Framework Setup Script
# PowerShell version for better compatibility

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "NIFTY Options Trading Framework Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Set project root directory
$PROJECT_ROOT = "C:\cursor\options\niftyopt"
Set-Location $PROJECT_ROOT

# Function to check Python installation
function Test-PythonInstallation {
    Write-Host "[1/8] Checking Python installation..." -ForegroundColor Yellow
    
    # Check common Python locations
    $pythonPaths = @(
        "python",
        "python3",
        "py",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python312\python.exe",
        "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python311\python.exe"
    )
    
    foreach ($path in $pythonPaths) {
        try {
            $version = & $path --version 2>$null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Found Python: $version" -ForegroundColor Green
                $script:PythonPath = $path
                return $true
            }
        } catch {
            continue
        }
    }
    
    Write-Host "ERROR: Python is not installed or not found in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.12+ from https://www.python.org/" -ForegroundColor Red
    return $false
}

# Function to create virtual environment
function New-VirtualEnvironment {
    Write-Host "[2/8] Creating virtual environment..." -ForegroundColor Yellow
    
    if (Test-Path "venv") {
        Write-Host "Virtual environment already exists. Removing old one..." -ForegroundColor Yellow
        Remove-Item -Path "venv" -Recurse -Force
    }
    
    try {
        & $PythonPath -m venv venv
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Virtual environment created successfully" -ForegroundColor Green
            return $true
        }
    } catch {
        Write-Host "ERROR: Failed to create virtual environment" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        return $false
    }
    
    return $false
}

# Function to activate virtual environment
function Enable-VirtualEnvironment {
    Write-Host "[3/8] Activating virtual environment..." -ForegroundColor Yellow
    
    try {
        & .\venv\Scripts\Activate.ps1
        Write-Host "Virtual environment activated" -ForegroundColor Green
        return $true
    } catch {
        Write-Host "ERROR: Failed to activate virtual environment" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        return $false
    }
}

# Function to upgrade pip
function Update-Pip {
    Write-Host "[4/8] Upgrading pip..." -ForegroundColor Yellow
    
    try {
        & .\venv\Scripts\python.exe -m pip install --upgrade pip
        if ($LASTEXITCODE -eq 0) {
            Write-Host "pip upgraded successfully" -ForegroundColor Green
            return $true
        }
    } catch {
        Write-Host "ERROR: Failed to upgrade pip" -ForegroundColor Red
        return $false
    }
    
    return $false
}

# Function to install dependencies
function Install-Dependencies {
    Write-Host "[5/8] Installing project dependencies..." -ForegroundColor Yellow
    
    if (-not (Test-Path "requirements.txt")) {
        Write-Host "ERROR: requirements.txt not found" -ForegroundColor Red
        return $false
    }
    
    try {
        & .\venv\Scripts\pip.exe install -r requirements.txt
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Dependencies installed successfully" -ForegroundColor Green
            return $true
        }
    } catch {
        Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        return $false
    }
    
    return $false
}

# Function to verify installation
function Test-Installation {
    Write-Host "[6/8] Verifying installation..." -ForegroundColor Yellow
    
    $packages = @("pandas", "numpy", "sklearn", "yfinance")
    
    foreach ($package in $packages) {
        try {
            $version = & .\venv\Scripts\python.exe -c "import ${package}; print(f'${package}: {${package}.__version__}')"
            Write-Host $version -ForegroundColor Green
        } catch {
            Write-Host "WARNING: $package not properly installed" -ForegroundColor Yellow
        }
    }
    
    return $true
}

# Function to setup environment
function Initialize-Environment {
    Write-Host "[7/8] Setting up environment variables..." -ForegroundColor Yellow
    
    if (-not (Test-Path ".env")) {
        if (Test-Path "env_template.txt") {
            Copy-Item "env_template.txt" ".env"
            Write-Host "Created .env file from template" -ForegroundColor Green
        } else {
            Write-Host "WARNING: env_template.txt not found" -ForegroundColor Yellow
        }
        
        Write-Host ""
        Write-Host "IMPORTANT: Edit .env file with your Dhan API credentials:" -ForegroundColor Cyan
        Write-Host "- DHAN_CLIENT_ID=your_client_id" -ForegroundColor Cyan
        Write-Host "- DHAN_ACCESS_TOKEN=your_access_token" -ForegroundColor Cyan
        Write-Host ""
    } else {
        Write-Host ".env file already exists" -ForegroundColor Green
    }
    
    return $true
}

# Function to verify project
function Test-ProjectSetup {
    Write-Host "[8/8] Running project verification..." -ForegroundColor Yellow
    
    if (Test-Path "verify_project_root.py") {
        try {
            & .\venv\Scripts\python.exe verify_project_root.py
            if ($LASTEXITCODE -eq 0) {
                Write-Host "Project verification passed" -ForegroundColor Green
            } else {
                Write-Host "WARNING: Project verification failed" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "WARNING: Could not run project verification" -ForegroundColor Yellow
        }
    } else {
        Write-Host "WARNING: verify_project_root.py not found" -ForegroundColor Yellow
    }
    
    return $true
}

# Main execution
try {
    $success = $true
    
    # Step 1: Check Python
    if (-not (Test-PythonInstallation)) {
        $success = $false
    }
    
    # Step 2: Create virtual environment
    if ($success -and -not (New-VirtualEnvironment)) {
        $success = $false
    }
    
    # Step 3: Activate virtual environment
    if ($success -and -not (Enable-VirtualEnvironment)) {
        $success = $false
    }
    
    # Step 4: Upgrade pip
    if ($success -and -not (Update-Pip)) {
        $success = $false
    }
    
    # Step 5: Install dependencies
    if ($success -and -not (Install-Dependencies)) {
        $success = $false
    }
    
    # Step 6: Verify installation
    if ($success) {
        Test-Installation
    }
    
    # Step 7: Setup environment
    if ($success) {
        Initialize-Environment
    }
    
    # Step 8: Verify project
    if ($success) {
        Test-ProjectSetup
    }
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    if ($success) {
        Write-Host "Setup Complete!" -ForegroundColor Green
    } else {
        Write-Host "Setup Failed! Please check the errors above." -ForegroundColor Red
    }
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    if ($success) {
        Write-Host "Next Steps:" -ForegroundColor Cyan
        Write-Host "1. Edit .env file with your Dhan API credentials" -ForegroundColor White
        Write-Host "2. Run: .\venv\Scripts\Activate.ps1" -ForegroundColor White
        Write-Host "3. Run: python scripts/test_dhan_connection.py" -ForegroundColor White
        Write-Host "4. Run: python scripts/module1_sanity_check.py" -ForegroundColor White
        Write-Host ""
        Write-Host "To activate environment in future:" -ForegroundColor Cyan
        Write-Host "  cd $PROJECT_ROOT" -ForegroundColor White
        Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White
    }
    
} catch {
    Write-Host "ERROR: Unexpected error during setup" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

Write-Host ""
Write-Host "Press any key to continue..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
