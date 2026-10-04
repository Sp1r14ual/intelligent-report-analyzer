$projectRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $projectRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   Starting Apache Superset & PostgreSQL Infrastructure " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check WSL Docker first, then fall back to Windows native Docker
$usedWsl = $false
$wslDistro = "Ubuntu"

try {
    $wslCheck = & wsl.exe -d $wslDistro -u root -e which docker 2>$null
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($wslCheck)) {
        $usedWsl = $true
        Write-Host "[OK] Detected Docker inside WSL ($wslDistro)!" -ForegroundColor Green
    }
} catch {
    $usedWsl = $false
}

if ($usedWsl) {
    Write-Host "Ensuring Docker daemon is active in WSL..." -ForegroundColor Yellow
    & wsl.exe -d $wslDistro -u root -e bash -c "service docker status >/dev/null 2>&1 || service docker start"
    
    $driveLetter = $projectRoot.ToString().Substring(0, 1).ToLower()
    $subPath = $projectRoot.ToString().Substring(3).Replace('\', '/')
    $wslPath = "/mnt/$driveLetter/$subPath"
    
    Write-Host "Launching containers via Docker Compose in WSL..." -ForegroundColor Cyan
    & wsl.exe -d $wslDistro -u root -e bash -c "cd '$wslPath' && docker compose -f docker-compose.superset.yml up -d"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] docker compose in WSL failed!" -ForegroundColor Red
        pause
        exit 1
    }
} else {
    # Native Windows Docker Desktop fallback
    $dockerPaths = @(
        "C:\Users\Sp1r14ual\AppData\Local\Programs\DockerDesktop\resources\bin",
        "C:\Program Files\Docker\Docker\resources\bin",
        "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin"
    )

    $dockerBin = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerBin) {
        foreach ($p in $dockerPaths) {
            if (Test-Path "$p\docker.exe") {
                $env:PATH = "$p;$env:PATH"
                Write-Host "[OK] Found Docker at: $p" -ForegroundColor Green
                break
            }
        }
    }

    $dockerBin = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerBin) {
        Write-Host "[ERROR] Docker not found neither in WSL nor in Windows PATH!" -ForegroundColor Red
        pause
        exit 1
    }

    Write-Host "Checking Docker daemon status..." -ForegroundColor Yellow
    $daemonRunning = $false
    try {
        $null = & docker info 2>&1
        if ($LASTEXITCODE -eq 0) { $daemonRunning = $true }
    } catch {
        $daemonRunning = $false
    }

    if (-not $daemonRunning) {
        Write-Host "Docker daemon is not running." -ForegroundColor Yellow
        $desktopApp = "C:\Users\Sp1r14ual\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe"
        if (Test-Path $desktopApp) {
            Write-Host "Starting Docker Desktop: $desktopApp..." -ForegroundColor Cyan
            Start-Process -FilePath $desktopApp
            Write-Host "Waiting for Docker daemon to initialize..." -ForegroundColor Yellow
            $waitCount = 0
            while (-not $daemonRunning -and $waitCount -lt 40) {
                Start-Sleep -Seconds 3
                $waitCount++
                try {
                    $null = & docker info 2>&1
                    if ($LASTEXITCODE -eq 0) {
                        $daemonRunning = $true
                        Write-Host "[OK] Docker daemon is ready!" -ForegroundColor Green
                        break
                    }
                } catch {}
                Write-Host "." -NoNewline -ForegroundColor Gray
            }
            Write-Host ""
        }
        
        if (-not $daemonRunning) {
            Write-Host "Please start Docker Desktop manually and wait until it is ready." -ForegroundColor Red
            pause
            exit 1
        }
    }

    Write-Host ""
    Write-Host "Launching containers (Superset, PostgreSQL, Redis)..." -ForegroundColor Cyan
    & docker compose -f docker-compose.superset.yml up -d

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] docker compose failed!" -ForegroundColor Red
        pause
        exit 1
    }
}

# 4. Wait for Superset healthcheck
Write-Host ""
Write-Host "Waiting for Apache Superset on http://localhost:8088 ..." -ForegroundColor Yellow
Write-Host "Initial startup may take 30-60 seconds for db migrations..." -ForegroundColor Gray

$supersetReady = $false
$attempts = 0
while (-not $supersetReady -and $attempts -lt 45) {
    Start-Sleep -Seconds 3
    $attempts++
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:8088/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($resp.StatusCode -eq 200) {
            $supersetReady = $true
            break
        }
    } catch {}
    Write-Host "   ...initializing ($($attempts * 3)s)..." -ForegroundColor Gray
}

# 5. Populate analytics schema with report data
Write-Host ""
Write-Host "Initializing PostgreSQL analytics schema and seeding report data..." -ForegroundColor Cyan
$pythonExe = "$projectRoot\.venv\Scripts\python.exe"
if (Test-Path $pythonExe) {
    & $pythonExe "$projectRoot\scripts\init_postgres_analytics.py"
} elseif (Test-Path "$projectRoot\.venv\bin\python") {
    $driveLetter = $projectRoot.ToString().Substring(0, 1).ToLower()
    $subPath = $projectRoot.ToString().Substring(3).Replace('\', '/')
    $wslP = "/mnt/$driveLetter/$subPath"
    & wsl.exe -d $wslDistro -u root -e bash -c "cd '$wslP' && .venv/bin/python scripts/init_postgres_analytics.py"
} else {
    python "$projectRoot\scripts\init_postgres_analytics.py"
}

Write-Host ""
Write-Host "========================================================" -ForegroundColor Green
Write-Host "  [SUCCESS] Apache Superset & PostgreSQL are ready!     " -ForegroundColor Green
Write-Host "  URL:      http://localhost:8088                       " -ForegroundColor Cyan
Write-Host "  Username: admin                                       " -ForegroundColor White
Write-Host "  Password: admin                                       " -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "You can now open Streamlit (Dashboards tab) and build dashboards!" -ForegroundColor Yellow
Write-Host ""
pause
