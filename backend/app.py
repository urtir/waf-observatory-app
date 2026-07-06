from datetime import datetime
import csv
from functools import lru_cache
from pathlib import Path
import subprocess
import sys
import logging

from flask import Flask, jsonify, render_template, request, send_file

log = logging.getLogger("waf")

from config import (
    COMPARE_RESULTS_DIR,
    DATASET_GOLDEN_CSV_PATH,
    DATASET_LOG_PATH,
    MODSEC_AUDIT_LOG_PATH,
    REPORTS_DIR,
    SQLITE_PATH,
    WORKSPACE_ROOT,
)
from services.database import (
    get_analyses_by_ids, get_executive_summary_by_id, get_recent_analyses,
    get_recent_executive_summaries, init_db, save_analysis_rows,
    save_executive_summary, save_raw_logs, get_raw_logs,
    delete_analysis, delete_executive_summary,
    save_dataset_evaluation, get_dataset_evaluations, delete_dataset_evaluation,
    save_stat_comparison, get_stat_comparisons, delete_stat_comparison,
    get_task, get_active_tasks, get_recent_tasks,
)
from services.task_manager import submit_task, task_progress
import json as _json
from services.dataset_repository import load_joined_dataset, load_joined_dataset_custom
from services.lmstudio_client import LMStudioClient
from services.metrics import compute_text_metrics, summarize_metrics
from services.pdf_export import export_analysis_to_pdf, export_analysis_to_pdf_with_summary, export_compare_stats_to_pdf, export_single_analysis_to_pdf
from services.prompt_builder import build_exact_prompt, build_executive_summary_from_analyses
from services.realtime_logs import read_recent_transactions


ALLOWED_MODELS = {"google/gemma-3-4b", "qwen/qwen3-4b-2507"}
COMPARE_FILES = {
    "descriptive": "descriptive_stats.csv",
    "shapiro": "shapiro_results.csv",
    "inferential": "inferential_results.csv",
    "summary": "metrics_summary.csv",
}


def _parse_float(raw_value: str | None) -> float | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _load_csv_records(filename: str, source_dir: Path | None = None) -> list[dict[str, str]]:
    base = source_dir or COMPARE_RESULTS_DIR
    path = base / filename
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file_obj:
        return list(csv.DictReader(file_obj))


def _metric_winner(diff_qwen_minus_gemma: float | None) -> str:
    if diff_qwen_minus_gemma is None:
        return "-"
    if diff_qwen_minus_gemma > 0:
        return "Qwen"
    if diff_qwen_minus_gemma < 0:
        return "Gemma"
    return "Seri"


def _build_compare_highlights(inferential_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    highlights: list[dict[str, str]] = []
    for row in inferential_rows:
        metric = str(row.get("metric") or "-")
        significant = str(row.get("significant") or "False").lower() == "true"
        diff = _parse_float(row.get("mean_diff_qwen_minus_gemma"))
        winner = _metric_winner(diff)
        p_holm = _parse_float(row.get("p_holm"))
        effect_size = _parse_float(row.get("effect_size"))
        highlights.append(
            {
                "metric": metric,
                "winner": winner,
                "significant": "Ya" if significant else "Tidak",
                "p_holm": "-" if p_holm is None else f"{p_holm:.6g}",
                "effect_size": "-" if effect_size is None else f"{effect_size:.4f}",
                "test": str(row.get("test") or "-"),
            }
        )
    return highlights


def _build_quick_conclusions(inferential_rows: list[dict[str, str]]) -> list[str]:
    conclusions: list[str] = []
    if not inferential_rows:
        return conclusions

    metric_map = {str(row.get("metric") or ""): row for row in inferential_rows}

    quality_metrics = ["rouge1_f1", "rouge2_f1", "rougel_f1", "bertscore_f1"]
    gemma_quality_wins = 0
    for metric in quality_metrics:
        row = metric_map.get(metric)
        if not row:
            continue
        if str(row.get("significant") or "False").lower() == "true":
            diff = _parse_float(row.get("mean_diff_qwen_minus_gemma"))
            if diff is not None and diff < 0:
                gemma_quality_wins += 1

    meteor_row = metric_map.get("meteor")
    latency_row = metric_map.get("latency_ms")

    if gemma_quality_wins >= 3:
        conclusions.append(
            "Gemma unggul pada mayoritas metrik kesesuaian ringkasan (ROUGE/BERTScore) dan perbedaannya signifikan."
        )

    if meteor_row:
        diff = _parse_float(meteor_row.get("mean_diff_qwen_minus_gemma"))
        significant = str(meteor_row.get("significant") or "False").lower() == "true"
        if diff is not None and diff > 0 and significant:
            conclusions.append("Qwen unggul pada METEOR secara signifikan.")

    if latency_row:
        diff = _parse_float(latency_row.get("mean_diff_qwen_minus_gemma"))
        significant = str(latency_row.get("significant") or "False").lower() == "true"
        if diff is not None and diff > 0 and significant:
            conclusions.append("Gemma lebih cepat (latency lebih rendah) secara signifikan.")

    return conclusions


def _metric_label(metric_key: str) -> str:
    labels = {
        "rouge1_f1": "ROUGE-1 F1",
        "rouge2_f1": "ROUGE-2 F1",
        "rougel_f1": "ROUGE-L F1",
        "meteor": "METEOR",
        "bertscore_f1": "BERTScore F1",
        "latency_ms": "Latency (ms)",
    }
    return labels.get(metric_key, metric_key)


def _build_metric_interpretations(
    shapiro_rows: list[dict[str, str]], inferential_rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    shapiro_map = {str(row.get("metric") or ""): row for row in shapiro_rows}
    interpretations: list[dict[str, str]] = []

    for row in inferential_rows:
        metric = str(row.get("metric") or "")
        if not metric:
            continue

        shapiro = shapiro_map.get(metric, {})
        normality = str(shapiro.get("normality") or "-")
        test_name = str(row.get("test") or "-")
        significant = str(row.get("significant") or "False").lower() == "true"
        diff = _parse_float(row.get("mean_diff_qwen_minus_gemma"))
        winner = _metric_winner(diff)

        if winner == "Gemma":
            direction = "Gemma lebih tinggi"
        elif winner == "Qwen":
            direction = "Qwen lebih tinggi"
        else:
            direction = "Tidak ada perbedaan rata-rata"

        if significant:
            verdict = "Perbedaan signifikan"
        else:
            verdict = "Perbedaan tidak signifikan"

        p_holm = _parse_float(row.get("p_holm"))
        p_holm_text = "-" if p_holm is None else f"{p_holm:.6g}"

        interpretations.append(
            {
                "metric": _metric_label(metric),
                "normality": normality,
                "test": test_name,
                "winner": winner,
                "verdict": verdict,
                "direction": direction,
                "effect_size": "-"
                if _parse_float(row.get("effect_size")) is None
                else f"{float(row.get('effect_size')):.4f}",
                "text": (
                    f"{_metric_label(metric)}: normalitas={normality}, uji={test_name}, "
                    f"{verdict.lower()} (p-holm={p_holm_text}), "
                    f"arah perbedaan={direction}."
                ),
            }
        )

    return interpretations


def _save_eval_csv(path: Path, items: list[dict]) -> None:
    fieldnames = ["tx_id", "model_key", "generated_summary", "golden_summary", "latency_ms",
                  "rouge1_f1", "rouge2_f1", "rougel_f1", "meteor", "bertscore_f1"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for item in items:
            row = {"model_key": item.get("model", ""), **item}
            writer.writerow(row)


@lru_cache(maxsize=1)
def get_dataset_rows_cached() -> list[dict[str, str]]:
    return load_joined_dataset()


_CUSTOM_LOG_PATH = None
_CUSTOM_GOLDEN_CSV_PATH = None
_CUSTOM_DATASET_ROWS = None
_CUSTOM_MISSING_TXIDS = []
_LAST_EVAL_CSV_PATH = None


def _worker_dataset_eval(task_id: str, db_path: Path, model: str, target_rows: list[dict]) -> dict:
    from services.database import update_task as _upd
    log = logging.getLogger("task.dataset_eval")
    log.info("[%s] Mulai evaluasi dataset: model=%s, txid=%d", task_id, model, len(target_rows))
    client = LMStudioClient()
    items: list[dict] = []
    rows_to_save: list[dict] = []

    for i, row in enumerate(target_rows):
        _upd(db_path, task_id, progress=i, current_item=f"Menganalisis {row['tx_id']} ({i+1}/{len(target_rows)})")
        prompt = build_exact_prompt(row["raw_log"])
        generated_summary, latency_ms = client.summarize(model, prompt)
        metrics = compute_text_metrics(row["golden_summary"], generated_summary)

        item = {
            "tx_id": row["tx_id"], "raw_log": row["raw_log"],
            "golden_summary": row["golden_summary"], "generated_summary": generated_summary,
            "latency_ms": round(latency_ms, 3), **metrics,
        }
        items.append(item)
        rows_to_save.append({
            "mode": "dataset", "model_key": model, "tx_id": row["tx_id"],
            "raw_log": row["raw_log"], "golden_summary": row["golden_summary"],
            "generated_summary": generated_summary, "latency_ms": round(latency_ms, 3),
            "rouge1_f1": item["rouge1_f1"], "rouge2_f1": item["rouge2_f1"],
            "rougel_f1": item["rougel_f1"], "meteor": item["meteor"],
            "bertscore_f1": item["bertscore_f1"],
        })

    ids = save_analysis_rows(db_path, rows_to_save)
    for idx, saved_id in enumerate(ids):
        items[idx]["analysis_id"] = saved_id

    global _LAST_EVAL_CSV_PATH
    csv_filename = f"eval_{model.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    csv_path = REPORTS_DIR / csv_filename
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    _save_eval_csv(csv_path, items)
    _LAST_EVAL_CSV_PATH = csv_path

    log_fn = _CUSTOM_LOG_PATH.name if _CUSTOM_LOG_PATH else DATASET_LOG_PATH.name
    golden_fn = _CUSTOM_GOLDEN_CSV_PATH.name if _CUSTOM_GOLDEN_CSV_PATH else DATASET_GOLDEN_CSV_PATH.name
    save_dataset_evaluation(db_path, model, log_fn, golden_fn, len(items),
                            summarize_metrics(items), str(csv_path))

    return {
        "model": model, "count": len(items),
        "metrics_summary": summarize_metrics(items),
        "items": items,
        "bertscore_enabled": any(i.get("bertscore_f1") is not None for i in items),
        "csv_path": str(csv_path), "csv_filename": csv_filename,
    }


def _worker_realtime_analyze(task_id: str, db_path: Path, model: str, selected: list[dict]) -> dict:
    from services.database import update_task as _upd
    log = logging.getLogger("task.realtime")
    log.info("[%s] Mulai analisis realtime: model=%s, rows=%d", task_id, model, len(selected))
    client = LMStudioClient()
    outputs: list[dict] = []
    rows_to_save: list[dict] = []

    for i, row in enumerate(selected):
        tx_id = str(row.get("tx_id") or "")
        raw_log = str(row.get("raw_log") or "")
        if not raw_log.strip():
            continue
        _upd(db_path, task_id, progress=i, current_item=f"Menganalisis {tx_id} ({i+1}/{len(selected)})")

        prompt = build_exact_prompt(raw_log)
        generated_summary, latency_ms = client.summarize(model, prompt)

        item = {"tx_id": tx_id, "generated_summary": generated_summary,
                "latency_ms": round(latency_ms, 3), "raw_log": raw_log}
        outputs.append(item)
        rows_to_save.append({
            "mode": "realtime", "model_key": model, "tx_id": tx_id, "raw_log": raw_log,
            "golden_summary": None, "generated_summary": generated_summary,
            "latency_ms": round(latency_ms, 3),
            "rouge1_f1": None, "rouge2_f1": None, "rougel_f1": None, "meteor": None, "bertscore_f1": None,
        })

    ids = save_analysis_rows(db_path, rows_to_save)
    for idx, saved_id in enumerate(ids):
        outputs[idx]["analysis_id"] = saved_id

    return {"model": model, "count": len(outputs), "items": outputs}


def _worker_exec_summary(task_id: str, db_path: Path, model: str, analyses: list[dict]) -> dict:
    from services.database import update_task as _upd
    log = logging.getLogger("task.exec_summary")
    log.info("[%s] Mulai executive summary: model=%s, temuan=%d", task_id, model, len(analyses))
    _upd(db_path, task_id, progress=0, current_item="Generating executive summary...")

    prompt = build_executive_summary_from_analyses(analyses)
    client = LMStudioClient(timeout_sec=600)
    generated_text, latency_ms = client.summarize(model, prompt, max_tokens=32768)

    analysis_ids = [a.get("analysis_id") for a in analyses if a.get("analysis_id")]
    summary_id = save_executive_summary(
        db_path, model, len(analyses), generated_text, round(latency_ms, 3), analysis_ids=analysis_ids
    )

    return {
        "id": summary_id, "model": model,
        "executive_summary": generated_text,
        "latency_ms": round(latency_ms, 3), "log_count": len(analyses),
    }


def create_app() -> Flask:
    app = Flask(__name__)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )
    app.logger.setLevel(logging.INFO)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    init_db(SQLITE_PATH)

    import threading
    def _preload_bert():
        from services.metrics import _get_bert_scorer
        log.info("Pre-loading BERT model ke RAM...")
        _get_bert_scorer()
        log.info("BERT model siap!")
    threading.Thread(target=_preload_bert, daemon=True).start()

    @app.before_request
    def _log_request():
        if request.path.startswith("/api/"):
            log.info("%s %s", request.method, request.path)

    @app.get("/")
    def dataset_page() -> str:
        return render_template("dataset_metrics.html")

    @app.get("/realtime")
    def realtime_page() -> str:
        return render_template("realtime_logs.html")

    @app.get("/docs")
    def docs_page() -> str:
        return render_template("documentation.html")

    @app.get("/compare")
    def compare_page() -> str:
        return render_template("compare_models.html")

    @app.get("/api/health")
    def health() -> tuple:
        return jsonify({"status": "ok"}), 200

    @app.get("/api/models")
    def models() -> tuple:
        client = LMStudioClient()
        model_items = client.list_models()
        filtered = [model for model in model_items if model.get("id") in ALLOWED_MODELS]
        return jsonify({"models": filtered}), 200

    @app.get("/api/dataset/info")
    def dataset_info() -> tuple:
        rows = get_dataset_rows_cached()
        return jsonify({"rows": len(rows)}), 200

    @app.get("/api/dataset/source")
    def dataset_source() -> tuple:
        if _CUSTOM_DATASET_ROWS is not None:
            rows = _CUSTOM_DATASET_ROWS
        else:
            rows = get_dataset_rows_cached()
        return (
            jsonify(
                {
                    "rows": len(rows),
                    "raw_log_path": str(_CUSTOM_LOG_PATH or DATASET_LOG_PATH),
                    "golden_csv_path": str(_CUSTOM_GOLDEN_CSV_PATH or DATASET_GOLDEN_CSV_PATH),
                    "missing_txids": _CUSTOM_MISSING_TXIDS,
                    "is_custom": _CUSTOM_DATASET_ROWS is not None,
                }
            ),
            200,
        )

    @app.post("/api/dataset/configure")
    def dataset_configure() -> tuple:
        global _CUSTOM_LOG_PATH, _CUSTOM_GOLDEN_CSV_PATH, _CUSTOM_DATASET_ROWS, _CUSTOM_MISSING_TXIDS

        log_file = request.files.get("log_file")
        golden_file = request.files.get("golden_file")

        if not log_file or not golden_file:
            return jsonify({"error": "Upload file log dan golden CSV wajib diisi"}), 400

        upload_dir = REPORTS_DIR / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        log_path = upload_dir / log_file.filename
        csv_path = upload_dir / golden_file.filename
        log_file.save(str(log_path))
        golden_file.save(str(csv_path))

        try:
            rows, missing = load_joined_dataset_custom(log_path, csv_path)
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": f"Format CSV tidak valid: {exc}"}), 400
        except Exception as exc:
            return jsonify({"error": f"Gagal memuat dataset: {exc}"}), 500

        _CUSTOM_LOG_PATH = log_path
        _CUSTOM_GOLDEN_CSV_PATH = csv_path
        _CUSTOM_DATASET_ROWS = rows
        _CUSTOM_MISSING_TXIDS = missing

        return jsonify({"ok": True, "rows": len(rows), "missing_txids": missing, "errors": [],
                        "log_filename": log_file.filename, "golden_filename": golden_file.filename}), 200

    @app.post("/api/dataset/reset")
    def dataset_reset() -> tuple:
        global _CUSTOM_LOG_PATH, _CUSTOM_GOLDEN_CSV_PATH, _CUSTOM_DATASET_ROWS, _CUSTOM_MISSING_TXIDS
        _CUSTOM_LOG_PATH = None
        _CUSTOM_GOLDEN_CSV_PATH = None
        _CUSTOM_DATASET_ROWS = None
        _CUSTOM_MISSING_TXIDS = []
        return jsonify({"ok": True}), 200

    @app.get("/api/dataset/rows")
    def dataset_rows() -> tuple:
        rows = _CUSTOM_DATASET_ROWS if _CUSTOM_DATASET_ROWS is not None else get_dataset_rows_cached()
        items = []
        for row in rows:
            request_line = ""
            for line in row["raw_log"].splitlines():
                if line.startswith(("GET ", "POST ", "PUT ", "DELETE ", "PATCH ", "HEAD ")):
                    request_line = line
                    break
            items.append(
                {
                    "tx_id": row["tx_id"],
                    "request_line": request_line,
                    "golden_summary": row["golden_summary"],
                    "raw_log_length": len(row["raw_log"]),
                }
            )
        return jsonify({"count": len(items), "items": items}), 200

    @app.get("/api/dataset/tx/<tx_id>")
    def dataset_tx_detail(tx_id: str) -> tuple:
        rows = _CUSTOM_DATASET_ROWS if _CUSTOM_DATASET_ROWS is not None else get_dataset_rows_cached()
        found = next((row for row in rows if row["tx_id"] == tx_id), None)
        if not found:
            return jsonify({"error": "tx_id tidak ditemukan"}), 404
        return jsonify(found), 200

    @app.post("/api/evaluate/dataset")
    def evaluate_dataset() -> tuple:
        payload = request.get_json(silent=True) or {}
        model = str(payload.get("model") or "").strip()
        limit = int(payload.get("limit") or 10)
        offset = int(payload.get("offset") or 0)

        if model not in ALLOWED_MODELS:
            return jsonify({"error": "Model tidak valid"}), 400

        rows = get_dataset_rows_cached()
        batch = rows[offset : offset + max(1, limit)]

        client = LMStudioClient()
        items: list[dict] = []
        rows_to_save: list[dict] = []

        for row in batch:
            prompt = build_exact_prompt(row["raw_log"])
            generated_summary, latency_ms = client.summarize(model, prompt)
            metrics = compute_text_metrics(row["golden_summary"], generated_summary)

            item = {
                "tx_id": row["tx_id"],
                "raw_log": row["raw_log"],
                "golden_summary": row["golden_summary"],
                "generated_summary": generated_summary,
                "latency_ms": round(latency_ms, 3),
                **metrics,
            }
            items.append(item)

            rows_to_save.append(
                {
                    "mode": "dataset",
                    "model_key": model,
                    "tx_id": row["tx_id"],
                    "raw_log": row["raw_log"],
                    "golden_summary": row["golden_summary"],
                    "generated_summary": generated_summary,
                    "latency_ms": round(latency_ms, 3),
                    "rouge1_f1": item["rouge1_f1"],
                    "rouge2_f1": item["rouge2_f1"],
                    "rougel_f1": item["rougel_f1"],
                    "meteor": item["meteor"],
                    "bertscore_f1": item["bertscore_f1"],
                }
            )

        ids = save_analysis_rows(SQLITE_PATH, rows_to_save)
        for idx, saved_id in enumerate(ids):
            items[idx]["analysis_id"] = saved_id

        return (
            jsonify(
                {
                    "model": model,
                    "count": len(items),
                    "metrics_summary": summarize_metrics(items),
                    "items": items,
                    "bertscore_enabled": any(i.get("bertscore_f1") is not None for i in items),
                }
            ),
            200,
        )

    @app.post("/api/evaluate/dataset-selected")
    def evaluate_dataset_selected() -> tuple:
        payload = request.get_json(silent=True) or {}
        model = str(payload.get("model") or "").strip()
        selected_txids = payload.get("selected_txids") or []

        if model not in ALLOWED_MODELS:
            return jsonify({"error": "Model tidak valid"}), 400
        if not isinstance(selected_txids, list) or not selected_txids:
            return jsonify({"error": "selected_txids wajib diisi"}), 400

        all_rows = _CUSTOM_DATASET_ROWS if _CUSTOM_DATASET_ROWS is not None else get_dataset_rows_cached()
        rows_by_id = {row["tx_id"]: row for row in all_rows}
        target_rows = [rows_by_id[txid] for txid in selected_txids if txid in rows_by_id]

        if not target_rows:
            return jsonify({"error": "Tidak ada tx_id valid untuk dianalisis"}), 400

        task_id = submit_task(SQLITE_PATH, "dataset_eval", len(target_rows), "dataset",
                              _worker_dataset_eval, model, target_rows)
        return jsonify({"task_id": task_id, "total": len(target_rows)}), 200

    @app.get("/api/logs/realtime")
    def logs_realtime() -> tuple:
        limit = int(request.args.get("limit", "500"))
        file_rows = read_recent_transactions(MODSEC_AUDIT_LOG_PATH, limit=max(1, min(limit, 5000)))
        save_raw_logs(SQLITE_PATH, file_rows)
        rows = get_raw_logs(SQLITE_PATH, limit=max(1, min(limit, 5000)))
        return jsonify({"count": len(rows), "items": rows}), 200

    @app.post("/api/analyze/realtime")
    def analyze_realtime() -> tuple:
        payload = request.get_json(silent=True) or {}
        model = str(payload.get("model") or "").strip()
        selected = payload.get("selected_rows") or []

        if model not in ALLOWED_MODELS:
            return jsonify({"error": "Model tidak valid"}), 400
        if not isinstance(selected, list) or not selected:
            return jsonify({"error": "selected_rows wajib diisi"}), 400

        valid_rows = [r for r in selected if str(r.get("raw_log") or "").strip()]
        if not valid_rows:
            return jsonify({"error": "Tidak ada raw_log valid"}), 400

        task_id = submit_task(SQLITE_PATH, "realtime_analyze", len(valid_rows), "realtime",
                              _worker_realtime_analyze, model, valid_rows)
        return jsonify({"task_id": task_id, "total": len(valid_rows)}), 200

    @app.post("/api/analyze/executive-summary")
    def executive_summary() -> tuple:
        payload = request.get_json(silent=True) or {}
        model = str(payload.get("model") or "").strip()
        analyses = payload.get("analyses") or []

        if model not in ALLOWED_MODELS:
            return jsonify({"error": "Model tidak valid"}), 400
        if not isinstance(analyses, list) or not analyses:
            return jsonify({"error": "analyses wajib diisi"}), 400

        task_id = submit_task(SQLITE_PATH, "exec_summary", len(analyses), "realtime",
                              _worker_exec_summary, model, analyses)
        return jsonify({"task_id": task_id, "total": len(analyses)}), 200

    @app.get("/api/tasks/<task_id>")
    def get_task_status(task_id: str) -> tuple:
        task = get_task(SQLITE_PATH, task_id)
        if not task:
            return jsonify({"error": "Task tidak ditemukan"}), 404
        return jsonify(task), 200

    @app.get("/api/tasks/active")
    def get_active() -> tuple:
        page = request.args.get("page")
        tasks = get_active_tasks(SQLITE_PATH, page_origin=page)
        return jsonify({"tasks": tasks}), 200

    @app.get("/api/tasks/recent")
    def get_recent() -> tuple:
        page = request.args.get("page")
        limit = int(request.args.get("limit", "20"))
        tasks = get_recent_tasks(SQLITE_PATH, limit=limit, page_origin=page)
        return jsonify({"tasks": tasks}), 200

    @app.get("/api/history/analyses")
    def history_analyses() -> tuple:
        limit = int(request.args.get("limit", "50"))
        rows = get_recent_analyses(SQLITE_PATH, mode="realtime", limit=max(1, min(limit, 200)))
        return jsonify({"count": len(rows), "items": rows}), 200

    @app.get("/api/history/executive-summaries")
    def history_executive_summaries() -> tuple:
        limit = int(request.args.get("limit", "20"))
        rows = get_recent_executive_summaries(SQLITE_PATH, limit=max(1, min(limit, 50)))
        for row in rows:
            ids_raw = row.get("analysis_ids")
            row["analysis_ids_list"] = _json.loads(ids_raw) if ids_raw else []
        return jsonify({"count": len(rows), "items": rows}), 200

    @app.get("/api/history/executive-summaries/<int:summary_id>")
    def history_executive_summary_detail(summary_id: int) -> tuple:
        summary = get_executive_summary_by_id(SQLITE_PATH, summary_id)
        if not summary:
            return jsonify({"error": "Data executive summary tidak ditemukan"}), 404

        ids_raw = summary.get("analysis_ids")
        analysis_ids = _json.loads(ids_raw) if ids_raw else []
        analyses = get_analyses_by_ids(SQLITE_PATH, analysis_ids) if analysis_ids else []
        summary["analyses"] = analyses
        return jsonify(summary), 200

    @app.post("/api/history/analyses/<int:analysis_id>/delete")
    def delete_analysis_endpoint(analysis_id: int) -> tuple:
        deleted = delete_analysis(SQLITE_PATH, analysis_id)
        if not deleted:
            return jsonify({"error": "Data tidak ditemukan"}), 404
        return jsonify({"ok": True}), 200

    @app.post("/api/history/executive-summaries/<int:summary_id>/delete")
    def delete_exec_summary_endpoint(summary_id: int) -> tuple:
        deleted = delete_executive_summary(SQLITE_PATH, summary_id)
        if not deleted:
            return jsonify({"error": "Data tidak ditemukan"}), 404
        return jsonify({"ok": True}), 200

    @app.post("/api/reports/pdf")
    def reports_pdf() -> tuple:
        payload = request.get_json(silent=True) or {}
        analysis_ids = payload.get("analysis_ids") or []
        executive_summary = payload.get("executive_summary")
        if not isinstance(analysis_ids, list) or not analysis_ids:
            return jsonify({"error": "analysis_ids wajib diisi"}), 400

        ids = [int(i) for i in analysis_ids]
        rows = get_analyses_by_ids(SQLITE_PATH, ids)
        if not rows:
            return jsonify({"error": "Data analisis tidak ditemukan"}), 404

        filename = f"waf_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        target = REPORTS_DIR / filename

        if executive_summary:
            output_path = export_analysis_to_pdf_with_summary(
                target, rows, "Laporan Analisis WAF Realtime", executive_summary=executive_summary
            )
        else:
            output_path = export_analysis_to_pdf(target, rows, "Laporan Analisis WAF Realtime")

        return send_file(Path(output_path), as_attachment=True, download_name=filename)

    @app.get("/api/history/analyses/<int:analysis_id>/pdf")
    def history_analysis_pdf(analysis_id: int) -> tuple:
        rows = get_analyses_by_ids(SQLITE_PATH, [analysis_id])
        if not rows:
            return jsonify({"error": "Data analisis tidak ditemukan"}), 404

        row = rows[0]
        filename = f"waf_analysis_{row.get('tx_id', 'detail')}_{analysis_id}.pdf"
        target = REPORTS_DIR / filename
        output_path = export_single_analysis_to_pdf(target, row)
        return send_file(Path(output_path), as_attachment=True, download_name=filename)

    @app.get("/api/history/executive-summaries/<int:summary_id>/pdf")
    def history_exec_summary_pdf(summary_id: int) -> tuple:
        summary = get_executive_summary_by_id(SQLITE_PATH, summary_id)
        if not summary:
            return jsonify({"error": "Data executive summary tidak ditemukan"}), 404

        ids_raw = summary.get("analysis_ids")
        analysis_ids = _json.loads(ids_raw) if ids_raw else []
        rows = get_analyses_by_ids(SQLITE_PATH, analysis_ids) if analysis_ids else []

        filename = f"waf_exec_summary_{summary_id}.pdf"
        target = REPORTS_DIR / filename

        if rows:
            output_path = export_analysis_to_pdf_with_summary(
                target, rows, "Laporan Analisis WAF - Executive Summary",
                executive_summary=summary.get("executive_summary", ""),
            )
        else:
            output_path = export_analysis_to_pdf_with_summary(
                target, [], "Laporan Analisis WAF - Executive Summary",
                executive_summary=summary.get("executive_summary", ""),
            )
        return send_file(Path(output_path), as_attachment=True, download_name=filename)

    @app.post("/api/prompt/preview")
    def prompt_preview() -> tuple:
        payload = request.get_json(silent=True) or {}
        raw_log = str(payload.get("raw_log") or "")
        prompt = build_exact_prompt(raw_log)
        return jsonify({"prompt": prompt}), 200

    @app.get("/api/evaluate/download-csv")
    def download_eval_csv() -> tuple:
        path_str = request.args.get("path", "")
        if path_str:
            csv_path = Path(path_str)
        elif _LAST_EVAL_CSV_PATH:
            csv_path = _LAST_EVAL_CSV_PATH
        else:
            return jsonify({"error": "Belum ada CSV evaluasi. Jalankan evaluasi terlebih dahulu."}), 404
        if not csv_path.exists():
            return jsonify({"error": f"File CSV tidak ditemukan: {csv_path}"}), 404
        return send_file(csv_path, as_attachment=True, download_name=csv_path.name)

    @app.get("/api/history/dataset-evaluations")
    def history_dataset_evaluations() -> tuple:
        limit = int(request.args.get("limit", "50"))
        rows = get_dataset_evaluations(SQLITE_PATH, limit=max(1, min(limit, 200)))
        return jsonify({"count": len(rows), "items": rows}), 200

    @app.post("/api/history/dataset-evaluations/<int:eval_id>/delete")
    def delete_dataset_eval(eval_id: int) -> tuple:
        deleted = delete_dataset_evaluation(SQLITE_PATH, eval_id)
        if not deleted:
            return jsonify({"error": "Data tidak ditemukan"}), 404
        return jsonify({"ok": True}), 200

    @app.get("/api/history/stat-comparisons")
    def history_stat_comparisons() -> tuple:
        limit = int(request.args.get("limit", "50"))
        rows = get_stat_comparisons(SQLITE_PATH, limit=max(1, min(limit, 200)))
        return jsonify({"count": len(rows), "items": rows}), 200

    @app.post("/api/history/stat-comparisons/<int:comp_id>/delete")
    def delete_stat_comp(comp_id: int) -> tuple:
        deleted = delete_stat_comparison(SQLITE_PATH, comp_id)
        if not deleted:
            return jsonify({"error": "Data tidak ditemukan"}), 404
        return jsonify({"ok": True}), 200

    @app.get("/api/compare/all")
    def compare_all() -> tuple:
        src = COMPARE_RESULTS_DIR
        descriptive_rows = _load_csv_records(COMPARE_FILES["descriptive"], src)
        shapiro_rows = _load_csv_records(COMPARE_FILES["shapiro"], src)
        inferential_rows = _load_csv_records(COMPARE_FILES["inferential"], src)
        summary_rows = _load_csv_records(COMPARE_FILES["summary"], src)
        interpretations = _build_metric_interpretations(shapiro_rows, inferential_rows)

        missing_files = [
            filename
            for filename in COMPARE_FILES.values()
            if not (src / filename).exists()
        ]

        return (
            jsonify(
                {
                    "source_dir": str(src),
                    "missing_files": missing_files,
                    "descriptive": descriptive_rows,
                    "shapiro": shapiro_rows,
                    "inferential": inferential_rows,
                    "summary": summary_rows,
                    "highlights": _build_compare_highlights(inferential_rows),
                    "conclusions": _build_quick_conclusions(inferential_rows),
                    "interpretations": interpretations,
                }
            ),
            200,
        )

    @app.post("/api/compare/report-pdf")
    def compare_report_pdf() -> tuple:
        src = COMPARE_RESULTS_DIR
        descriptive_rows = _load_csv_records(COMPARE_FILES["descriptive"], src)
        shapiro_rows = _load_csv_records(COMPARE_FILES["shapiro"], src)
        inferential_rows = _load_csv_records(COMPARE_FILES["inferential"], src)
        summary_rows = _load_csv_records(COMPARE_FILES["summary"], src)

        if not (descriptive_rows or shapiro_rows or inferential_rows or summary_rows):
            return jsonify({"error": "Data statistik tidak tersedia untuk diekspor"}), 404

        filename = f"waf_compare_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        target = REPORTS_DIR / filename
        output_path = export_compare_stats_to_pdf(
            output_path=target,
            title="Laporan Komparasi Statistik Qwen vs Gemma",
            summary_rows=summary_rows,
            shapiro_rows=shapiro_rows,
            descriptive_rows=descriptive_rows,
            inferential_rows=inferential_rows,
            highlights=_build_compare_highlights(inferential_rows),
            conclusions=_build_quick_conclusions(inferential_rows),
            interpretations=_build_metric_interpretations(shapiro_rows, inferential_rows),
        )

        return send_file(Path(output_path), as_attachment=True, download_name=filename)

    @app.post("/api/compare/recompute")
    def compare_recompute() -> tuple:
        qwen_csv = COMPARE_RESULTS_DIR / "results_qwen_qwen3_4b.csv"
        gemma_csv = COMPARE_RESULTS_DIR / "results_google_gemma_3_4b.csv"
        script_path = WORKSPACE_ROOT / "run_inferential_tests.py"

        if not script_path.exists():
            return jsonify({"error": f"Script statistik tidak ditemukan: {script_path}"}), 404
        if not qwen_csv.exists() or not gemma_csv.exists():
            return (
                jsonify(
                    {
                        "error": (
                            "File hasil inferensi model belum lengkap. "
                            "Pastikan results_qwen_qwen3_4b.csv dan "
                            "results_google_gemma_3_4b.csv tersedia."
                        )
                    }
                ),
                400,
            )

        cmd = [
            sys.executable,
            str(script_path),
            "--qwen-csv",
            str(qwen_csv),
            "--gemma-csv",
            str(gemma_csv),
            "--out-dir",
            str(COMPARE_RESULTS_DIR),
        ]

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except Exception as exc:
            return jsonify({"error": f"Gagal menjalankan analisis statistik: {exc}"}), 500

        if proc.returncode != 0:
            message = (proc.stderr or proc.stdout or "Unknown error").strip()
            if "ModuleNotFoundError" in message and "scipy" in message:
                message = (
                    "Environment backend belum memiliki scipy. "
                    "Install dependency backend (pip install -r backend/requirements.txt) "
                    "lalu restart service backend."
                )
            return jsonify({"error": f"Analisis statistik gagal: {message}"}), 500

        src = COMPARE_RESULTS_DIR
        inferential_rows = _load_csv_records(COMPARE_FILES["inferential"], src)
        highlights = _build_compare_highlights(inferential_rows)
        conclusions = _build_quick_conclusions(inferential_rows)
        source_files = [f.name for f in src.glob("*.csv")] if src.exists() else []
        save_stat_comparison(SQLITE_PATH, str(src), source_files, highlights, conclusions)

        return (
            jsonify(
                {
                    "status": "ok",
                    "message": "Analisis statistik berhasil diperbarui.",
                    "stdout": (proc.stdout or "").strip(),
                    "out_dir": str(COMPARE_RESULTS_DIR),
                }
            ),
            200,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
