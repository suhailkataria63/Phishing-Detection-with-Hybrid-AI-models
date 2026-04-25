#!/usr/bin/env python3
"""Lightweight backend smoke checks for model loading and health diagnostics."""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from fastapi.testclient import TestClient


def _as_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    print(f"[smoke] project_root={project_root}")

    results: dict[str, object] = {
        "import_ok": False,
        "url_model_loaded": False,
        "email_model_loaded": False,
        "health_ok": False,
    }

    try:
        from app.backend.app.main import app, email_model, url_model

        results["import_ok"] = True
        print("[smoke] import app.backend.app.main: OK")
    except Exception as exc:
        results["import_error"] = _as_error(exc)
        print("[smoke] import failed")
        print(traceback.format_exc())
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 1

    # URL model load
    try:
        url_model.load()
        results["url_model_loaded"] = bool(url_model.is_ready())
        results["url_v1_loaded"] = bool(getattr(url_model, "v1_loaded", False))
        results["url_v2_loaded"] = bool(getattr(url_model, "v2_loaded", False))
        results["url_v1_error"] = str(getattr(url_model, "v1_error", ""))
        results["url_v2_error"] = str(getattr(url_model, "v2_error", ""))
        print(
            "[smoke] URL model load:",
            f"ready={results['url_model_loaded']} v1={results['url_v1_loaded']} v2={results['url_v2_loaded']}",
        )
    except Exception as exc:
        results["url_model_loaded"] = False
        results["url_model_error"] = _as_error(exc)
        print(f"[smoke] URL model load failed: {results['url_model_error']}")

    # Email model load
    try:
        email_model.load()
        results["email_model_loaded"] = bool(email_model.is_ready)
        results["email_model_meta"] = dict(email_model.meta)
        print(f"[smoke] Email model load: ready={results['email_model_loaded']}")
    except Exception as exc:
        results["email_model_loaded"] = False
        results["email_model_error"] = _as_error(exc)
        print(f"[smoke] Email model load failed: {results['email_model_error']}")

    # /health diagnostics
    try:
        client = TestClient(app)
        resp = client.get("/health")
        results["health_ok"] = resp.status_code == 200
        results["health_status_code"] = resp.status_code
        if resp.status_code == 200:
            payload = resp.json()
            results["health"] = {
                "status": payload.get("status"),
                "service": payload.get("service"),
                "url_model_loaded": payload.get("url_model_loaded"),
                "url_v1_loaded": payload.get("url_v1_loaded"),
                "url_v2_loaded": payload.get("url_v2_loaded"),
                "email_model_ready": payload.get("email_model_ready"),
                "url_model_error": payload.get("url_model_error"),
                "url_v1_error": payload.get("url_v1_error"),
                "url_v2_error": payload.get("url_v2_error"),
                "email_model_error": payload.get("email_model_error"),
            }
            print("[smoke] /health: OK")
        else:
            results["health_response"] = resp.text
            print(f"[smoke] /health failed status={resp.status_code}")
    except Exception as exc:
        results["health_ok"] = False
        results["health_error"] = _as_error(exc)
        print(f"[smoke] /health request failed: {results['health_error']}")

    print("\n[smoke] summary")
    print(json.dumps(results, indent=2, ensure_ascii=False))

    return 0 if results.get("import_ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
