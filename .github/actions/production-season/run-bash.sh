#!/usr/bin/env bash
# A queued or long-running job may reach this step after Chicago midnight.
set -euo pipefail
active=$(python3 -B -c 'from desktop_runtime.seasonal_policy import in_season; print(str(in_season()).lower())')
if [[ "$active" == false ]]; then
    echo "season_skipped=true" >> "$GITHUB_OUTPUT"
    echo "Jubilee production paused for winter."
    exit 0
fi
exec bash --noprofile --norc -e -o pipefail "$1"
