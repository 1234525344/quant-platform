import hashlib
import hmac
import logging
import os

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from telegram_client import send_message

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
app = FastAPI(docs_url=None, redoc_url=None)
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

def telegram(method, data):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    result = httpx.post(
        "https://api.telegram.org/bot" + token + "/" + method,
        json=data, timeout=20,
    )
    if result.status_code != 200:
        raise RuntimeError("Telegram request rejected with HTTP " + str(result.status_code))
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
        logging.error("Telegram webhook registration failed; verify Bot Token in Render")

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
        if CHAT_ID and chat_id != CHAT_ID:
            return {"ok": True}
        send_message(chat_id, "✅ Telegram 通知测试成功。Gmail 监测仍需授权。")
    return {"ok": True}

@app.post("/pubsub")
async def gmail_push(request: Request, authorization: str | None = Header(None)):
    from push_receiver import authorized_push, handle_notification
    authorized_push(authorization)
    return {"processed": handle_notification(await request.json(), CHAT_ID)}

@app.post("/admin/renew")
def renew_watch(x_admin_secret: str | None = Header(None)):
    from push_receiver import start_watch
    secret = os.getenv("ADMIN_SECRET", "")
    if not secret or not x_admin_secret or not hmac.compare_digest(x_admin_secret, secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"expiration": start_watch()}

@app.post("/admin/bootstrap")
def bootstrap(x_admin_secret: str | None = Header(None)):
    from mail_processor import scan
    secret = os.getenv("ADMIN_SECRET", "")
    if not secret or not x_admin_secret or not hmac.compare_digest(x_admin_secret, secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"marked": scan(CHAT_ID, bootstrap=True)}
