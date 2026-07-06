import re

from config import MAX_RAW_CHARS, PROMPT_PREFIX, PROMPT_SUFFIX

def _extract_request_info(raw_log: str) -> tuple[str, str]:
    request_line_match = re.search(r'^(GET|POST|PUT|DELETE|PATCH|HEAD)\s+[^\s]+', raw_log, re.MULTILINE)
    method = request_line_match.group(1) if request_line_match else "UNKNOWN"
    
    ip_match = re.search(r'^\[client\s+([^\]:]+)', raw_log, re.MULTILINE)
    ip = ip_match.group(1) if ip_match else "UNKNOWN"
    
    return method, ip


def build_exact_prompt(raw_tx_log: str) -> str:
    log_text = raw_tx_log.strip()
    if len(log_text) > MAX_RAW_CHARS:
        log_text = log_text[:MAX_RAW_CHARS] + "\n... [dipotong]"

    return (
        f"{PROMPT_PREFIX}\n\n"
        "<RAW_LOG>\n"
        f"{log_text}\n"
        "</RAW_LOG>\n\n"
        f"{PROMPT_SUFFIX}"
    )


EXECUTIVE_SUMMARY_SYSTEM = (
    "Anda adalah analis keamanan siber senior yang menyusun executive summary "
    "tentang kumpulan transaksi log serangan HTTP yang terdeteksi oleh Web Application Firewall (WAF) ModSecurity. "
    "Executive summary harus ditulis dalam Bahasa Indonesia formal, dalam bentuk paragraf yang mengalir "
    "(bukan bullet point), dan maksimal 1-3 paragraf. "
    "Bacalah seluruh temuan di bawah ini, lalu buatkan ringkasan yang mencakup: "
    "tren serangan utama, jenis serangan yang paling umum, teknik serangan yang digunakan, "
    "endpoint yang paling diserang, metode HTTP yang paling sering disalahgunakan, "
    "identifikasi IP penyerang utama (jika tersedia), tingkat keparahan umum, serta rekomendasi mitigasi penting."
)


def build_executive_summary_from_analyses(analyses: list[dict]) -> str:
    blocks: list[str] = []
    for idx, item in enumerate(analyses, start=1):
        tx_id = str(item.get("tx_id") or f"row-{idx}")
        generated_summary = str(item.get("generated_summary") or "").strip()
        raw_log = str(item.get("raw_log") or "")
        latency = item.get("latency_ms")
        latency_text = f"{latency:.1f}ms" if latency is not None else "-"
        
        method, ip = _extract_request_info(raw_log)

        if not generated_summary:
            continue

        block = (
            f"=== Temuan #{idx} | TXID: {tx_id} | IP: {ip} | Method: {method} | Latency: {latency_text} ===\n"
            f"{generated_summary}"
        )
        blocks.append(block)

    all_findings = "\n\n".join(blocks)

    return (
        f"{EXECUTIVE_SUMMARY_SYSTEM}\n\n"
        "Berikut adalah kumpulan temuan analisis insiden keamanan dari WAF ModSecurity:\n\n"
        "<FINDINGS>\n"
        f"{all_findings}\n"
        "</FINDINGS>\n\n"
        "Buatkan executive summary dalam 1-3 paragraf maksimal. Jangan gunakan bullet point. "
        "Ringkas semua temuan menjadi satu atau dua paragraf yang koheren, "
        "sertakan: pola serangan utama, jenis serangan paling umum, endpoint yang paling sering diserang, "
        "metode HTTP yang disalahgunakan, IP penyerang utama (jika ada pola yang konsisten), "
        "tingkat keparahan, dan rekomendasi mitigasi yang paling relevan."
    )
