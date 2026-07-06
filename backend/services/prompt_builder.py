from config import MAX_RAW_CHARS, PROMPT_PREFIX, PROMPT_SUFFIX


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
    "Anda adalah analis keamanan siber senior yang menyusun executive summary komprehensif "
    "tentang kumpulan transaksi log serangan HTTP yang terdeteksi oleh Web Application Firewall (WAF) ModSecurity. "
    "Executive summary harus ditulis dalam Bahasa Indonesia formal, dalam bentuk paragraf yang mengalir "
    "(bukan bullet point), dan mencakup seluruh temuan secara lengkap dan mendalam. "
    "Jelaskan secara rinci: tren serangan yang teramati, jenis-jenis serangan yang ditemukan "
    "(SQL Injection, XSS, Remote Code Execution, Path Traversal, dll.), teknik dan pola serangan yang digunakan, "
    "target endpoint dan metode HTTP yang diserang, tingkat keparahan dan risiko masing-masing temuan, "
    "potensi dampak terhadap sistem jika serangan berhasil, serta rekomendasi mitigasi yang relevan. "
    "Tulis selengkap mungkin tanpa membatasi panjang output."
)


def build_executive_summary_from_analyses(analyses: list[dict]) -> str:
    blocks: list[str] = []
    for idx, item in enumerate(analyses, start=1):
        tx_id = str(item.get("tx_id") or f"row-{idx}")
        generated_summary = str(item.get("generated_summary") or "").strip()
        latency = item.get("latency_ms")
        latency_text = f"{latency:.1f}ms" if latency is not None else "-"

        if not generated_summary:
            continue

        block = (
            f"=== Temuan #{idx} | TXID: {tx_id} | Latency: {latency_text} ===\n"
            f"{generated_summary}"
        )
        blocks.append(block)

    all_findings = "\n\n".join(blocks)

    return (
        f"{EXECUTIVE_SUMMARY_SYSTEM}\n\n"
        "Berikut adalah kumpulan temuan analisis insiden keamanan dari WAF ModSecurity "
        "yang perlu Anda rangkum menjadi satu executive summary komprehensif:\n\n"
        "<FINDINGS>\n"
        f"{all_findings}\n"
        "</FINDINGS>\n\n"
        "Buatlah executive summary yang komprehensif dan selengkap mungkin dalam bentuk paragraf. "
        "Jangan gunakan bullet point. Jelaskan semua temuan dari awal hingga akhir secara mendalam, "
        "termasuk pola serangan, jenis serangan, tingkat keparahan, dan rekomendasi mitigasi."
    )
