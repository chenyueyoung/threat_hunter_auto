"""项目配置。"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

REPORT_URL = "https://www.threathunter.cn/report"

HEADLESS = False
BROWSER_CHANNEL = "chrome"
PAGE_TIMEOUT_MS = 60_000
ARTICLE_LINK_SELECTOR = 'a[href*="/blog/"]'
TITLE_KEYWORDS = ["黑产", "灰产", "骗贷", "信贷", "贷款", "欺诈", "贷"]
RUN_DAY = 25

HISTORY_FILE = BASE_DIR / "history.json"
HTML_OUTPUT_DIR = BASE_DIR / ".tmp" / "html"
BROWSER_PROFILE_DIR = BASE_DIR / ".browser_profile"
