#!/usr/bin/env bash
set -u

PREFERRED_PYTHON="/Library/Frameworks/Python.framework/Versions/3.10/bin/python3"
PYTHON_PATH_FILE=".python_path"

if [ -x "$PREFERRED_PYTHON" ]; then
  PYTHON="$PREFERRED_PYTHON"
else
  PYTHON="$(command -v python3 || true)"
fi

if [ -z "${PYTHON:-}" ]; then
  echo "未找到 Python 3。请先安装 Python 3.10+，然后重新执行：bash setup.sh"
  exit 1
fi

echo "使用 Python：$PYTHON"
"$PYTHON" --version

if ! "$PYTHON" -m pip install \
  --timeout 600 \
  --retries 10 \
  --disable-pip-version-check \
  -r requirements.txt; then
  echo "依赖安装失败，可能是网络超时。请稍后重新执行：bash setup.sh"
  exit 1
fi

if "$PYTHON" -c "import playwright" >/dev/null 2>&1; then
  echo "Playwright Python 包已安装。"
else
  echo "Playwright 安装异常，请重新执行：bash setup.sh"
  exit 1
fi

if "$PYTHON" -m playwright install chromium; then
  echo "Chromium 浏览器依赖已准备完成。"
else
  echo "Chromium 安装失败，可能是网络超时。请稍后重新执行：bash setup.sh"
  exit 1
fi

mkdir -p output/package
printf "%s\n" "$PYTHON" > "$PYTHON_PATH_FILE"

echo "安装完成。以后运行：bash start.sh"
