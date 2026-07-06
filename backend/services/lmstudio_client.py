import time
import requests

from config import LM_STUDIO_BASE_URL


class LMStudioClient:
    def __init__(self, base_url: str | None = None, timeout_sec: int = 120):
        self.base_url = (base_url or LM_STUDIO_BASE_URL).rstrip("/")
        self.timeout_sec = timeout_sec

    def list_models(self) -> list[dict]:
        response = requests.get(f"{self.base_url}/v1/models", timeout=self.timeout_sec)
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", [])

    def summarize(self, model: str, prompt: str, max_tokens: int | None = None) -> tuple[str, float]:
        started = time.perf_counter()
        body: dict = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        response = requests.post(
            f"{self.base_url}/v1/chat/completions",
            timeout=self.timeout_sec,
            json=body,
        )

        if not response.ok:
            error_detail = ""
            try:
                err = response.json()
                error_detail = err.get("error", {}).get("message", "") or str(err)
            except Exception:
                error_detail = response.text[:500]
            raise RuntimeError(
                f"LM Studio error {response.status_code}: {error_detail}"
            )

        latency_ms = (time.perf_counter() - started) * 1000.0
        payload = response.json()

        choices = payload.get("choices", [])
        if not choices:
            return "", latency_ms

        message = choices[0].get("message", {})
        content = message.get("content", "")
        return str(content).strip(), latency_ms
