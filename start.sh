#!/usr/bin/env bash
set -e

PYTHON_PATH_FILE=".python_path"

if [ -f "$PYTHON_PATH_FILE" ]; then
  PYTHON="$(cat "$PYTHON_PATH_FILE")"
else
  PYTHON="$(command -v python3 || true)"
fi

if [ -z "${PYTHON:-}" ] || [ ! -x "$PYTHON" ]; then
  echo "未找到可用 Python。请先执行：bash setup.sh"
  exit 1
fi

if ! "$PYTHON" - <<'PY'
import sys

if sys.version_info < (3, 10):
    raise SystemExit(1)
PY
then
  echo "当前 Python 版本低于 3.10。请先安装 Python 3.10+，然后重新执行：bash setup.sh"
  exit 1
fi

"$PYTHON" run.py "$@"
