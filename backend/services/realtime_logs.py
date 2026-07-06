import re
from datetime import datetime
from pathlib import Path

_TS_RE = re.compile(r"\[(\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}\s[+\-]\d{4})\]")


def _parse_tx_block(block_lines: list[str]) -> dict | None:
    if not block_lines:
        return None

    tx_id = None
    timestamp_raw = ""
    timestamp_iso = ""
    raw_request = ""
    status_line = ""
    messages: list[str] = []

    for i, line in enumerate(block_lines):
        if line.startswith("---") and line.endswith("---A--"):
            tx_id = line[3:-5]
            if i + 1 < len(block_lines):
                ts_match = _TS_RE.search(block_lines[i + 1])
                if ts_match:
                    timestamp_raw = ts_match.group(1)
                    try:
                        dt = datetime.strptime(timestamp_raw, "%d/%b/%Y:%H:%M:%S %z")
                        timestamp_iso = dt.isoformat()
                    except ValueError:
                        timestamp_iso = timestamp_raw
        if line.startswith("---") and line.endswith("---B--"):
            req = []
            j = i + 1
            while j < len(block_lines) and not block_lines[j].startswith("---"):
                req.append(block_lines[j])
                j += 1
            raw_request = "\n".join(req).strip()
        if line.startswith("---") and line.endswith("---F--"):
            resp = []
            j = i + 1
            while j < len(block_lines) and not block_lines[j].startswith("---"):
                resp.append(block_lines[j])
                j += 1
            status_line = (resp[0].strip() if resp else "")
        if "ModSecurity:" in line:
            messages.append(line.strip())

    if not tx_id:
        return None

    return {
        "tx_id": tx_id,
        "timestamp": timestamp_iso,
        "timestamp_raw": timestamp_raw,
        "request": raw_request,
        "status": status_line,
        "alerts": messages,
        "raw_log": "\n".join(block_lines).strip(),
    }


def read_recent_transactions(log_path: Path, limit: int = 50) -> list[dict]:
    if not log_path.exists():
        return []

    with log_path.open("r", encoding="utf-8", errors="ignore") as file_obj:
        lines = [line.rstrip("\n") for line in file_obj]

    blocks: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        if line.startswith("---") and line.endswith("---A--"):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
            if line.startswith("---") and line.endswith("---Z--"):
                blocks.append(current)
                current = []

    if current:
        blocks.append(current)

    rows = []
    for block in reversed(blocks[-limit:]):
        parsed = _parse_tx_block(block)
        if parsed:
            rows.append(parsed)

    return rows
