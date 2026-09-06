param([string]$Root = 'C:\JubileeCams')
# Reads inventory/status only. Does not start cameras, read credentials, change
# scheduled tasks, alter execution policy, or upload any data.
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    throw 'Jubilee runtime folder does not exist. Stop and resolve the canonical path.'
}
$report = [ordered]@{
    schema_version = '2.0'
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    root = $Root
    mode = 'READ_ONLY_INVENTORY_NO_SECRET_CONTENTS'
    executables = @()
    python_files = @()
    scheduled_tasks = @()
    camera_products = @()
    archive_manifests = @()
    google_inventory_accessed = $false
    runtime_modified = $false
}
foreach ($name in @('python', 'py', 'ffmpeg')) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue | Select-Object -First 1
    $report.executables += [ordered]@{name=$name; found=($null -ne $cmd); path=$(if ($cmd) {$cmd.Source} else {$null})}
}
Get-ChildItem -LiteralPath $Root -File -Filter '*.py' | ForEach-Object {
    $report.python_files += [ordered]@{
        name=$_.Name; bytes=$_.Length; modified_at_utc=$_.LastWriteTimeUtc.ToString('o')
        sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower()
    }
}
try {
    Get-ScheduledTask | Where-Object {$_.TaskName -match 'Jubilee'} | ForEach-Object {
        $task = $_
        $info = Get-ScheduledTaskInfo -TaskName $task.TaskName -TaskPath $task.TaskPath
        # Intentionally exclude Arguments and Principal: they can reveal secrets or account details.
        $actions = @($task.Actions | ForEach-Object {[ordered]@{execute=$_.Execute; working_directory=$_.WorkingDirectory}})
        $report.scheduled_tasks += [ordered]@{
            name=$task.TaskName; state=[string]$task.State; task_path=$task.TaskPath
            last_run=$info.LastRunTime.ToString('o'); next_run=$info.NextRunTime.ToString('o')
            last_result=$info.LastTaskResult; missed_runs=$info.NumberOfMissedRuns; actions=$actions
        }
    }
} catch {
    $report.scheduled_task_inventory_error = $_.Exception.GetType().Name
}
foreach ($relative in @('frames\status.json', 'frames\burst_status.json', 'frames\vision.json', 'live_frames\live_status.json', 'live_frames\status.json')) {
    $path = Join-Path $Root $relative
    $entry = [ordered]@{file=$relative; exists=(Test-Path -LiteralPath $path -PathType Leaf)}
    if ($entry.exists) {
        try {
            $obj = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
            $entry.capture_time_ct = $obj.capture_time_ct
            $entry.modified_at_utc = (Get-Item -LiteralPath $path).LastWriteTimeUtc.ToString('o')
            $entry.cameras = @()
            if ($obj.cameras) {
                foreach ($property in $obj.cameras.PSObject.Properties) {
                    $cam = $property.Value
                    # Only whitelisted health fields. No URLs, device IDs, names of people or errors with secrets.
                    $entry.cameras += [ordered]@{
                        camera_id=$property.Name; ok=$cam.ok; status=$cam.status
                        timestamp_ct=$cam.timestamp_ct; burst_count=$cam.burst_count
                        has_human_sensor_score=($null -ne $cam.human_sensor_score)
                    }
                }
            }
        } catch {
            $entry.parse_error = $_.Exception.GetType().Name
        }
    }
    $report.camera_products += $entry
}
foreach ($relative in @('archive\latest_manifest.json', 'frames\archive_manifest.json', 'frames\burst_latest')) {
    $path = Join-Path $Root $relative
    $entry = [ordered]@{path=$relative; exists=(Test-Path -LiteralPath $path)}
    if ($entry.exists) {
        $item = Get-Item -LiteralPath $path
        $entry.modified_at_utc = $item.LastWriteTimeUtc.ToString('o')
        if ($item.PSIsContainer) {
            $entry.file_count = @(Get-ChildItem -LiteralPath $path -File).Count
        } else {
            $entry.bytes = $item.Length
        }
    }
    $report.archive_manifests += $entry
}
# Output only. Save locally or share this sanitized report; do not share configuration or credentials.
$report | ConvertTo-Json -Depth 8
