#!/bin/bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
env_file=${URBAN_ENV_FILE:-"$repo_root/.env"}

if [[ ! -r "$env_file" ]]; then
    echo "Credential file is not readable: $env_file" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
. "$env_file"
set +a

export URBAN_SYSTEM_CONFIG=${URBAN_SYSTEM_CONFIG:-"$repo_root/config.json"}
python_bin=${URBAN_PYTHON:-"$repo_root/.venv/bin/python"}
if [[ ! -x "$python_bin" ]]; then
    echo "Python interpreter is not executable: $python_bin" >&2
    exit 1
fi
cd "$repo_root"
exec "$python_bin" "$@"
