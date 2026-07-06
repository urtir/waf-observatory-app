from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = BASE_DIR.parent.parent

# Load environment variables from backend/.env first.
load_dotenv(BASE_DIR / ".env", override=False)

DATASET_LOG_PATH = Path(
    os.getenv(
        "DATASET_LOG_PATH",
        str(WORKSPACE_ROOT / "DATASET" / "owasp" / "01-Aug-2025" / "modsec_audit.anon.log"),
    )
)
DATASET_GOLDEN_CSV_PATH = Path(
    os.getenv(
        "DATASET_GOLDEN_CSV_PATH",
        str(WORKSPACE_ROOT / "DATASET1000_with_summary.csv"),
    )
)

LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234")
MODSEC_AUDIT_LOG_PATH = Path(os.getenv("MODSEC_AUDIT_LOG_PATH", "/var/log/modsecurity/audit.log"))
SQLITE_PATH = Path(os.getenv("SQLITE_PATH", str(BASE_DIR / "instance" / "app.db")))
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", str(BASE_DIR / "reports")))
COMPARE_RESULTS_DIR = Path(
    os.getenv(
        "COMPARE_RESULTS_DIR",
        str(WORKSPACE_ROOT / "HASIL" / "lmstudio_top1000_eval"),
    )
)

MAX_RAW_CHARS = 4000

# Prompt untuk golden summary - output HANYA ringkasan, tanpa preamble
PROMPT_PREFIX = (
    "Anda adalah analis keamanan siber. Buatkan golden summary tentang satu transaksi "
    "raw log ModSecurity berbahaya. Ringkasan harus mencakup: IP penyerang, metode HTTP, "
    "endpoint yang diserang, parameter mencurigakan, tujuan serangan, jenis serangan (SQLi, XSS, dll.), "
    "teknik yang digunakan, dampak potensial. "
    "Output HANYA ringkasan satu paragraf Bahasa Indonesia formal, TANPA preamble, TANPA header."
)
PROMPT_SUFFIX = "Ringkasan:"