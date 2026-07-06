import json
import logging
import threading
import uuid
from pathlib import Path

from services.database import create_task, update_task, get_task

log = logging.getLogger("task_manager")


def new_task_id() -> str:
    return uuid.uuid4().hex[:12]


def submit_task(db_path: Path, task_type: str, total: int, page_origin: str, fn, *args, **kwargs) -> str:
    task_id = new_task_id()
    create_task(db_path, task_id, task_type, total, page_origin)
    log.info("Task [%s] dibuat: type=%s, total=%d, page=%s", task_id, task_type, total, page_origin)

    def _run():
        try:
            log.info("Task [%s] mulai berjalan...", task_id)
            update_task(db_path, task_id, status="running", progress=0)
            result = fn(task_id, db_path, *args, **kwargs)
            update_task(db_path, task_id, status="done", progress=total, result=json.dumps(result))
            log.info("Task [%s] selesai!", task_id)
        except Exception as exc:
            update_task(db_path, task_id, status="error", error=str(exc))
            log.error("Task [%s] gagal: %s", task_id, exc)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return task_id


def task_progress(db_path: Path, task_id: str, progress: int, current_item: str = "") -> None:
    update_task(db_path, task_id, progress=progress, current_item=current_item)
