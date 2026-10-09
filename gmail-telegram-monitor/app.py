import hashlib
import hmac
import logging
import os

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from telegram_client import send_message

logging.basicConfig(level=logging.INFO)
app = FastAPI(docs_url=None, redoc_url=None)
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

def telegram(method, data):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    result = httpx.post(
        "https://api.telegram.org/bot" + token + "/" + method,
        json=data, timeout=20,
    )
    result.raise_for_status()
    return result.json()

def webhook_secret():
    return hashlib.sha256(os.environ["TELEGRAM_BOT_TOKEN"].encode()).hexdigest()

@app.on_event("startup")
def initialize():
    if not os.getenv("TELEGRAM_BOT_TOKEN"):
        logging.warning("Telegram setup pending")
        return
    try:
        telegram("setWebhook", {
            "url": "https://gmail-broker-alerts-lb.onrender.com/telegram",
            "secret_token": webhook_secret(),
        })
        logging.info("Telegram webhook registered")
    except Exception:
        logging.exception("Telegram webhook registration failed")

@app.get("/health")
def health():
    return {"ok": True, "mode": "broker_monitor",
            "telegram_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
            "chat_configured": bool(CHAT_ID),
            "gmail_configured": all(os.getenv(k) for k in (
                "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"))}

@app.post("/telegram")
async def telegram_hook(request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None)):
    expected = webhook_secret()
    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, expected):
        raise HTTPException(status_code=403, detail="Forbidden")
    event = await request.json()
    msg = event.get("message", {})
    chat = msg.get("chat", {})
    if chat.get("type") == "private" and msg.get("text", "").startswith("/start"):
        chat_id = str(chat["id"])
        logging.info("Telegram setup: private chat ID %s", chat_id)
        if CHAT_ID and chat_id != CHAT_ID:
            return {"ok": True}
        send_message(chat_id, "✅ Telegram 通知测试成功。Gmail 监测仍需授权。")
    return {"ok": True}
