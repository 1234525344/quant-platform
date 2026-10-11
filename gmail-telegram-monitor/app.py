# -*- coding: utf-8 -*-
import hashlib
import hmac
import logging
import os

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from telegram_client import send_message
from pydantic import BaseModel
from polling import STATE, BaselineRequired, run_poll
from mail_processor import ScanBusy

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
                "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")),
            "poll_configured": bool(os.getenv("POLL_SECRET")),
            "polling": dict(STATE)}


def authorize_poll(supplied):
    secret = os.getenv("POLL_SECRET", "")
    if not secret or not supplied or not hmac.compare_digest(supplied.encode(), secret.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")


class PollRequest(BaseModel):
    bootstrap: bool = False


@app.post("/admin/poll")
def poll(body: PollRequest = PollRequest(), x_poll_secret: str | None = Header(None)):
    authorize_poll(x_poll_secret)
    try:
        return {"ok": True, **run_poll(CHAT_ID, bootstrap=body.bootstrap)}
    except ScanBusy:
        raise HTTPException(status_code=409, detail="Scan already running")
    except BaselineRequired:
        raise HTTPException(status_code=409, detail="Baseline required")
    except Exception:
        raise HTTPException(status_code=503, detail="Polling failed; check monitor status")


@app.post("/admin/test-notification")
def test_notification(x_poll_secret: str | None = Header(None)):
    authorize_poll(x_poll_secret)
    if not CHAT_ID:
        raise HTTPException(status_code=503, detail="Chat not configured")
    try:
        send_message(CHAT_ID, "✅ Gmail → Telegram 定时监测连接测试成功。此消息是连接测试，不是新邮件通知。")
    except Exception:
        raise HTTPException(status_code=503, detail="Telegram delivery failed")
    return {"ok": True, "telegram_delivered": True}

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
        send_message(chat_id, "✅ Telegram 已连接。Gmail 定时监测状态可在服务健康页查看。")
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
