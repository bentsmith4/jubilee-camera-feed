$ErrorActionPreference = "Stop"

$Base = "C:\JubileeCams"
$TaskName = "Jubilee Live Cameras"
$ExpectedOldVersion = "2026-09-08-season-efficiency-timing-v1"
$ExpectedNewVersion = "2026-09-18-cache-compact-synthesis-v2"
$Commit = "665024dc2b4b44d4d40de1afccb88ee9db559dc3"
$RawUrl = "https://raw.githubusercontent.com/bentsmith4/jubilee-camera-feed/$Commit/desktop_runtime/analyze_frames.py"

$Live = Join-Path $Base "analyze_frames.py"
$Python = Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe"
if (-not (Test-Path $Python)) {
    $Python = (Get-Command python -ErrorAction Stop).Source
}

if (-not (Test-Path $Live)) {
    throw "Missing live analyzer: $Live"
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Rollback = Join-Path $Base ("rollback_" + $stamp + "_cost_opt")
$Downloaded = Join-Path $env:TEMP ("jubilee_analyze_frames_" + $stamp + ".py")
$CanaryLog = Join-Path $Rollback "analyze_canary.log"
$PipelineLog = Join-Path $Rollback "canonical_pipeline.log"

New-Item -ItemType Directory -Path $Rollback -Force | Out-Null
Copy-Item $Live (Join-Path $Rollback "analyze_frames.py.before") -Force

$current = Get-Content $Live -Raw
$currentVersion = $null
if ($current -match 'RUNTIME_VERSION\s*=\s*"([^"]+)"') {
    $currentVersion = $Matches[1]
}
Write-Host "Current runtime version: $currentVersion"

if ($currentVersion -eq $ExpectedNewVersion) {
    Write-Host "Cost optimization already installed. Running verification only."
} elseif ($currentVersion -ne $ExpectedOldVersion) {
    throw "Unexpected live analyzer version '$currentVersion'. Backup saved at $Rollback. No replacement made."
} else {
    Invoke-WebRequest -Uri $RawUrl -OutFile $Downloaded -UseBasicParsing
    $downloadedText = Get-Content $Downloaded -Raw
    if ($downloadedText -notmatch [regex]::Escape('RUNTIME_VERSION = "' + $ExpectedNewVersion + '"')) {
        throw "Downloaded analyzer does not contain expected runtime version."
    }
    if ($downloadedText -notmatch "prompt_cache_options" -or
        $downloadedText -notmatch "deterministic_quiet") {
        throw "Downloaded analyzer is missing expected cost-optimization controls."
    }

    & $Python -m py_compile $Downloaded
    if ($LASTEXITCODE -ne 0) {
        throw "Downloaded analyzer failed Python compilation."
    }

    Write-Host "Stopping existing Jubilee task..."
    try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction Stop } catch {
        schtasks.exe /End /TN $TaskName | Out-Null
    }
    Start-Sleep -Seconds 5

    Copy-Item $Downloaded $Live -Force
    Write-Host "Installed $ExpectedNewVersion"
}

# Ensure the service is stopped while the direct analyzer canary owns the API work.
try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch {}
Start-Sleep -Seconds 3

Write-Host "Running direct six-camera analysis canary against the latest retained burst..."
& $Python $Live *>&1 | Tee-Object -FilePath $CanaryLog
$canaryExit = $LASTEXITCODE

if ($canaryExit -ne 0) {
    Write-Host "Canary failed. Restoring prior analyzer."
    Copy-Item (Join-Path $Rollback "analyze_frames.py.before") $Live -Force
    try { Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop } catch {
        schtasks.exe /Run /TN $TaskName | Out-Null
    }
    throw "Deployment rolled back because analyze_frames.py canary failed. See $CanaryLog"
}

$visionPath = Join-Path $Base "frames\vision.json"
if (-not (Test-Path $visionPath)) {
    Copy-Item (Join-Path $Rollback "analyze_frames.py.before") $Live -Force
    try { Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop } catch {
        schtasks.exe /Run /TN $TaskName | Out-Null
    }
    throw "Canary produced no vision.json; deployment rolled back."
}

$vision = Get-Content $visionPath -Raw | ConvertFrom-Json
if ($vision.runtime_version -ne $ExpectedNewVersion) {
    Copy-Item (Join-Path $Rollback "analyze_frames.py.before") $Live -Force
    try { Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop } catch {
        schtasks.exe /Run /TN $TaskName | Out-Null
    }
    throw "Canary vision.json has runtime '$($vision.runtime_version)'; deployment rolled back."
}

$cameraCount = @($vision.cameras.PSObject.Properties).Count
Write-Host "Canary succeeded. vision.json runtime=$($vision.runtime_version), cameras=$cameraCount"

Write-Host "Running one fresh canonical capture/publish cycle..."
& $Python (Join-Path $Base "capture_publish.py") *>&1 | Tee-Object -FilePath $PipelineLog
$pipelineExit = $LASTEXITCODE

Write-Host "Restarting existing Jubilee task..."
try { Start-ScheduledTask -TaskName $TaskName -ErrorAction Stop } catch {
    schtasks.exe /Run /TN $TaskName | Out-Null
}
Start-Sleep -Seconds 5

$task = Get-ScheduledTask -TaskName $TaskName
$state = $task.State

Write-Host ""
Write-Host "============================================================"
if ($pipelineExit -eq 0) {
    Write-Host "JUBILEE COST OPTIMIZATION DEPLOYMENT SUCCESS"
} else {
    Write-Host "JUBILEE COST OPTIMIZATION INSTALLED; FRESH PIPELINE HAD A NONZERO EXIT"
}
Write-Host "Runtime: $ExpectedNewVersion"
Write-Host "Task: $TaskName = $state"
Write-Host "Backup: $Rollback"
Write-Host "Canary log: $CanaryLog"
Write-Host "Pipeline log: $PipelineLog"
Write-Host "Camera count in canary vision: $cameraCount"
Write-Host "============================================================"

if ($pipelineExit -ne 0) {
    Write-Host "The analyzer canary passed, so the new analyzer was kept. Review the canonical pipeline log for the separate capture/publish failure."
    exit 2
}
