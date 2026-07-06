import re
from pathlib import Path


TX_HEADER_RE = re.compile(r"^--(?P<txid>[0-9A-Za-z]+)-(?P<section>[A-Z])--$")


def parse_raw_transactions(log_path: Path) -> list[dict[str, str]]:
    transactions: list[dict[str, str]] = []
    current_txid = None
    current_lines: list[str] = []

    with log_path.open("r", encoding="utf-8", errors="ignore") as file_obj:
        for line in file_obj:
            line_clean = line.rstrip("\r\n")
            match = TX_HEADER_RE.match(line_clean)

            if match and match.group("section") == "A":
                if current_txid is not None:
                    transactions.append(
                        {
                            "tx_id": current_txid,
                            "raw_log": "".join(current_lines).strip(),
                        }
                    )
                current_txid = match.group("txid")
                current_lines = [line]
            elif current_txid is not None:
                current_lines.append(line)

    if current_txid is not None:
        transactions.append(
            {
                "tx_id": current_txid,
                "raw_log": "".join(current_lines).strip(),
            }
        )

    return transactions
