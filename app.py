"""提供遊戲頁與本機題庫更新 API；僅供 localhost 使用。"""
from __future__ import annotations

import hmac
import os
import secrets
from pathlib import Path
from threading import Lock, Thread

from flask import Flask, jsonify, request, send_from_directory

from scrape_dictionary import build_questions

ROOT = Path(__file__).parent
app = Flask(__name__)
state = {"running": False, "progress": 0, "message": "尚未開始更新。", "error": None}
state_lock = Lock()
# 每次啟動皆使用新密鑰；也可由環境變數提供，方便本機自動化。
CRAWL_AUTH_TOKEN = os.environ.get("CRAWL_AUTH_TOKEN") or secrets.token_urlsafe(32)


def update_state(progress: int, message: str) -> None:
    with state_lock:
        state.update(progress=progress, message=message)


def crawl_in_background() -> None:
    try:
        build_questions(progress=update_state)
    except Exception as error:  # 保留錯誤給畫面，避免背景執行緒靜默失敗。
        with state_lock:
            state.update(message="更新失敗。", error=str(error))
    finally:
        with state_lock:
            state["running"] = False


def is_authorized() -> bool:
    """僅接受由本機遊戲頁以自訂標頭送出的當次啟動密鑰。"""
    supplied = request.headers.get("X-Crawl-Token", "")
    return hmac.compare_digest(supplied, CRAWL_AUTH_TOKEN)


@app.get("/")
def index():
    return send_from_directory(ROOT, "index.html")


@app.get("/api/crawl-status")
def crawl_status():
    with state_lock:
        return jsonify(state)


@app.post("/api/refresh-questions")
def refresh_questions():
    if not is_authorized():
        return jsonify(error="更新密鑰無效。"), 401
    with state_lock:
        if state["running"]:
            return jsonify(state), 409
        state.update(running=True, progress=0, message="準備開始更新…", error=None)
    Thread(target=crawl_in_background, daemon=True).start()
    return jsonify(state), 202


@app.get("/<path:filename>")
def static_files(filename: str):
    return send_from_directory(ROOT, filename)


if __name__ == "__main__":
    print("\n題庫更新密鑰（本次啟動有效，請貼到遊戲頁）：")
    print(CRAWL_AUTH_TOKEN + "\n")
    app.run(host="127.0.0.1", port=8000, debug=False)
