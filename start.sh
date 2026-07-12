#!/usr/bin/env bash
set -e

PREFERRED_PYTHON="/Library/Frameworks/Python.framework/Versions/3.10/bin/python3"
PYTHON_PATH_FILE=".python_path"

if [ -f "$PYTHON_PATH_FILE" ]; then
  PYTHON="$(cat "$PYTHON_PATH_FILE")"
elif [ -x "$PREFERRED_PYTHON" ]; then
  PYTHON="$PREFERRED_PYTHON"
else
  PYTHON="$(command -v python3 || true)"
fi

if [ -z "${PYTHON:-}" ] || [ ! -x "$PYTHON" ]; then
  echo "未找到可用 Python。请先执行：bash setup.sh"
  exit 1
fi

"$PYTHON" run.py "$@"
