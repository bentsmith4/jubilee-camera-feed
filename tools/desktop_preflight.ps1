param(
    [string]$Root = 'C:\JubileeCams',
    [string]$Python = 'python',
    [switch]$Offline,
    [string]$PublishedCommit,
    [string]$PreviousMain
)
# One read-only acceptance entry point. No task starts/changes, camera calls,
# execution-policy changes, fetch/push, uploads, or report files. R2 GETs use
# existing local r2.json only; neither its values nor exception text are emitted.
$ErrorActionPreference = 'Stop'
$inventory = [ordered]@{ available=$false; tasks=@() }
try {
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    $tasks = @(Get-ScheduledTask -ErrorAction Stop)
    foreach ($task in $tasks) {
        $actions = @($task.Actions)
        # Inspect arguments locally only to detect additional capture owners.
        # Never serialize command lines, principals, task paths or directories.
        $captureAction = @($actions | Where-Object {
            $_.Arguments -match '(?i)(live_loop|capture_service|capture_publish|dawn_runner|burst_capture|live_capture)\.py'
        }).Count -gt 0
        if ($task.TaskName -notmatch '(?i)Jubilee|^Dawn Cameras$' -and -not $captureAction) { continue }
        $info = Get-ScheduledTaskInfo -TaskName $task.TaskName -TaskPath $task.TaskPath -ErrorAction Stop
        $actionMatches = $false
        if ($actions.Count -eq 1) {
            $action = $actions[0]
            $executable = [IO.Path]::GetFileName($action.Execute)
            $arg = ([string]$action.Arguments).Trim()
            $scriptArg = [regex]::Replace($arg, '^(?:(?:-u|-B)\s+)*', '')
            # Parse one script argument, rejecting extra arguments and quotes.
            # Normalize its directory by the SAME method as Root (including
            # Windows short-path aliases); never compare a raw command to Root.
            $scriptMatch = [regex]::Match($scriptArg, '^(?:"([^"]+)"|([^"\s]+))$')
            if ($scriptMatch.Success) {
                $scriptPath = $scriptMatch.Groups[1].Value
                if (-not $scriptPath) { $scriptPath = $scriptMatch.Groups[2].Value }
                if (-not [IO.Path]::IsPathRooted($scriptPath)) {
                    if ($action.WorkingDirectory) {
                        $scriptPath = [IO.Path]::Combine($action.WorkingDirectory, $scriptPath)
                    } else {
                        $scriptPath = ''
                    }
                }
                if ($scriptPath) {
                    $scriptRoot = [IO.Path]::GetFullPath([IO.Path]::GetDirectoryName($scriptPath)).TrimEnd('\')
                    $entry = [IO.Path]::GetFileName($scriptPath)
                    $actionMatches = ($executable -match '^(python|pythonw)(\.exe)?$') -and
                        ($scriptRoot -eq $rootFull) -and ($entry -in @('live_loop.py', 'capture_service.py'))
                }
            }
        }
        $role = if ($task.TaskName -eq 'Jubilee Live Cameras') { 'coordinator' } else { 'additional_capture_task' }
        $state = [string]$task.State
        if ($state -notin @('Running', 'Ready', 'Disabled', 'Queued')) { $state = 'Unknown' }
        $inventory.tasks += [ordered]@{
            role=$role; state=$state; enabled=[bool]$task.Settings.Enabled
            action_matches=[bool]$actionMatches
            last_run=$info.LastRunTime.ToUniversalTime().ToString('o')
            last_result=[long]$info.LastTaskResult; missed_runs=[long]$info.NumberOfMissedRuns
        }
    }
    $inventory.available = $true
} catch {
    # Partial inventory cannot prove that there is only one owner.
    $inventory = [ordered]@{ available=$false; tasks=@() }
}
try {
    $verifier = Join-Path $PSScriptRoot 'desktop_verify.py'
    $arguments = @('-B', $verifier, '--root', $Root, '--tasks-stdin')
    if ($Offline) { $arguments += '--offline' }
    if ($PublishedCommit) { $arguments += @('--published-commit', $PublishedCommit) }
    if ($PreviousMain) { $arguments += @('--previous-main', $PreviousMain) }
    # Capture all native output; emit only one parsed verifier report. Even a
    # missing Python dependency or startup traceback must not leak local paths.
    $raw = $inventory | ConvertTo-Json -Depth 5 -Compress | & $Python @arguments 2>$null
    $exitCode = $LASTEXITCODE
    $report = ($raw -join "`n") | ConvertFrom-Json
    if ($report.status -notin @('PASS', 'FAIL', 'NOT_VERIFIED')) { throw 'Invalid report' }
    $report | ConvertTo-Json -Depth 12
    exit $exitCode
} catch {
    '{"schema_version":"3.0","status":"NOT_VERIFIED","code":"verifier_unavailable"}'
    exit 2
}
