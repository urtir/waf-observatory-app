import csv
from pathlib import Path

from config import DATASET_GOLDEN_CSV_PATH, DATASET_LOG_PATH
from services.log_parser import parse_raw_transactions


def _pick_column(fieldnames: set[str], candidates: list[str], label: str) -> str:
    for candidate in candidates:
        if candidate in fieldnames:
            return candidate
    raise ValueError(
        f"Kolom wajib untuk '{label}' tidak ditemukan. Kandidat yang diterima: {candidates}. Kolom tersedia: {sorted(fieldnames)}"
    )


def load_golden_summary_map(csv_path: Path | None = None) -> dict[str, str]:
    target_path = csv_path or DATASET_GOLDEN_CSV_PATH
    result = {}

    with target_path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        fieldnames = set(reader.fieldnames or [])
        tx_col = _pick_column(fieldnames, ["tx_id", "TXID", "txid", "TxID"], "tx_id")
        summary_col = _pick_column(
            fieldnames,
            ["golden_summary", "Ringkasan", "ringkasan", "summary", "Summary"],
            "golden_summary",
        )

        for row in reader:
            tx_id = str(row.get(tx_col) or "").strip()
            golden_summary = str(row.get(summary_col) or "").strip()
            if tx_id:
                result[tx_id] = golden_summary

    return result


def load_joined_dataset() -> list[dict[str, str]]:
    if not DATASET_LOG_PATH.exists():
        raise FileNotFoundError(f"Raw log tidak ditemukan: {DATASET_LOG_PATH}")
    if not DATASET_GOLDEN_CSV_PATH.exists():
        raise FileNotFoundError(f"Golden CSV tidak ditemukan: {DATASET_GOLDEN_CSV_PATH}")

    transactions = parse_raw_transactions(DATASET_LOG_PATH)
    golden_map = load_golden_summary_map(DATASET_GOLDEN_CSV_PATH)

    rows: list[dict[str, str]] = []
    for item in transactions:
        tx_id = item["tx_id"]
        if tx_id in golden_map:
            rows.append(
                {
                    "tx_id": tx_id,
                    "raw_log": item["raw_log"],
                    "golden_summary": golden_map[tx_id],
                }
            )

    return rows


def load_joined_dataset_custom(log_path: Path, golden_csv_path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not log_path.exists():
        raise FileNotFoundError(f"Raw log tidak ditemukan: {log_path}")
    if not golden_csv_path.exists():
        raise FileNotFoundError(f"Golden CSV tidak ditemukan: {golden_csv_path}")

    transactions = parse_raw_transactions(log_path)
    golden_map = load_golden_summary_map(golden_csv_path)

    rows: list[dict[str, str]] = []
    missing_txids: list[str] = []
    for item in transactions:
        tx_id = item["tx_id"]
        if tx_id in golden_map:
            rows.append(
                {
                    "tx_id": tx_id,
                    "raw_log": item["raw_log"],
                    "golden_summary": golden_map[tx_id],
                }
            )
        else:
            missing_txids.append(tx_id)

    return rows, missing_txids
