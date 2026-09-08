$ErrorActionPreference = 'Stop'
$jubileeBase = 'C:\JubileeCams'
$target = Join-Path $jubileeBase 'publish_github.py'
$expectedOld = '5AD8CF4A04E70C2D24641FB523A718AEAF8481F54FB7086357E1B30C90D329FF'
$expectedNew = '96A9D7B9ED0E1C5EA5B46F02A214F601BFD02AC280D0851E7DE4EC629CAC5B85'
$actual = (Get-FileHash $target -Algorithm SHA256).Hash
if ($actual -eq $expectedNew) { Write-Output 'USAGE REPORTING ALREADY INSTALLED'; return }
if ($actual -ne $expectedOld) { throw 'Publisher changed since verification. No files installed.' }
$task = Get-ScheduledTask -TaskName 'Jubilee Live Cameras'
$python = @($task.Actions)[0].Execute
if (-not (Test-Path -LiteralPath $python)) { throw 'Scheduled Python executable not found.' }
$staging = Join-Path $jubileeBase ('usage_update_' + [guid]::NewGuid().ToString('N') + '.py')
$validator = Join-Path $jubileeBase ('usage_validate_' + [guid]::NewGuid().ToString('N') + '.py')
$backupDir = Join-Path $jubileeBase ('rollback_usage_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
try {
    Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/bentsmith4/jubilee-camera-feed/2c943e67d05edf45d932fef7075937639b438d41/desktop_runtime/publish_github.py' -OutFile $staging
    if ((Get-FileHash $staging -Algorithm SHA256).Hash -ne $expectedNew) { throw 'Download hash mismatch.' }
    & $python -m py_compile $staging
    if ($LASTEXITCODE -ne 0) { throw 'Python compilation failed.' }
    $check = @'
import runpy
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[2])
module = runpy.run_path(sys.argv[1])
summary = module["usage_summary"](Path(sys.argv[2]))
if summary["status"] != "available" or not summary["groups"]:
    raise RuntimeError("No usable usage records")
count = sum(group["logged_requests"] for group in summary["groups"])
print("LOCAL SUMMARY VERIFIED: " + str(count) + " logged requests")
'@
    [System.IO.File]::WriteAllText($validator, $check, [System.Text.UTF8Encoding]::new($false))
    & $python $validator $staging $jubileeBase
    if ($LASTEXITCODE -ne 0) { throw 'Local summary validation failed. Active publisher unchanged.' }
    if ((Get-FileHash $target -Algorithm SHA256).Hash -ne $expectedOld) { throw 'Publisher changed during staging.' }
    New-Item -ItemType Directory -Path $backupDir | Out-Null
    $backup = Join-Path $backupDir 'publish_github.py'
    # Atomic replacement: an already-running Python process retains its loaded code.
    [System.IO.File]::Replace($staging, $target, $backup)
    try {
        if ((Get-FileHash $target -Algorithm SHA256).Hash -ne $expectedNew) { throw 'Installed hash mismatch.' }
        if ((Get-FileHash $backup -Algorithm SHA256).Hash -ne $expectedOld) { throw 'Backup hash mismatch.' }
    } catch {
        [System.IO.File]::Replace($backup, $target, $null)
        throw
    }
    Write-Output ('VERIFIED BACKUP: ' + $backup)
    Write-Output 'USAGE REPORTING INSTALLED AND VERIFIED. No restart required.'
    Write-Output 'The next successful canonical publication will include api_usage_summary.json.'
} finally {
    if (Test-Path -LiteralPath $validator) { Remove-Item -LiteralPath $validator }
    if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging }
}
