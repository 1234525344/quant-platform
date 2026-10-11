# -*- coding: utf-8 -*-
import logging
import os
from datetime import datetime, timezone

from google.auth.exceptions import RefreshError
from gmail_client import api
from mail_processor import SCAN_LOCK, ScanBusy, scan_stats
from telegram_client import send_message

BASELINE_LABEL = "BROKER_MONITOR_BASELINE_READY"
STATE = {"last_attempt": None, "last_success": None, "status": "not_started",
         "baseline_ready": None, "last_result": None, "error_code": None}
_alerted_error = None


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class BaselineRequired(RuntimeError):
    pass


def run_poll(chat_id, bootstrap=False):
    global _alerted_error
    if not SCAN_LOCK.acquire(blocking=False):
        raise ScanBusy("Scan already running")
    try:
        STATE.update(last_attempt=utc_now(), status="running")
        if not chat_id:
            raise ValueError("Chat not configured")
        gmail = api()
        # Never accept credentials for another mailbox by accident.
        expected = os.environ["MONITORED_GMAIL"].strip().lower()
        actual = gmail.users().getProfile(userId="me").execute()["emailAddress"].lower()
        if actual != expected:
            raise ValueError("Mailbox mismatch")
        labels = gmail.users().labels().list(userId="me").execute().get("labels", [])
        ready = any(item["name"] == BASELINE_LABEL for item in labels)
        STATE["baseline_ready"] = ready
        if bootstrap:
            if ready:
                result = {"examined": 0, "sent": 0, "marked": 0, "automatic": 0}
            else:
                # Fixed installation cutoff, not restart time: a retry cannot
                # silently baseline newly arriving messages.
                cutoff = int(os.environ["POLL_BASELINE_BEFORE"])
                result = scan_stats(gmail, chat_id, bootstrap=True, before=cutoff)
                gmail.users().labels().create(userId="me", body={
                    "name": BASELINE_LABEL, "labelListVisibility": "labelHide",
                    "messageListVisibility": "hide"}).execute()
                STATE["baseline_ready"] = True
        else:
            if not ready:
                raise BaselineRequired("Baseline required")
            result = scan_stats(gmail, chat_id)
        recovering = _alerted_error is not None
        STATE.update(status="ok", last_success=utc_now(), last_result=result, error_code=None)
        _alerted_error = None
        if recovering:
            try:
                send_message(chat_id, "✅ Gmail 邮件监测已恢复，最近七天待处理邮件已完成补扫。")
            except Exception:
                logging.warning("Recovery notification unavailable")
        return result
    except BaselineRequired:
        STATE.update(status="baseline_required", error_code="baseline_required")
        raise
    except Exception as exc:
        code = "gmail_authorization" if isinstance(exc, RefreshError) else "scan_failed"
        STATE.update(status="error", error_code=code)
        logging.error("Polling failed: %s", code)
        if _alerted_error != code and chat_id:
            try:
                send_message(chat_id, "⚠️ Gmail 邮件监测失败（" + code + "）。请检查授权或 GitHub Actions 运行状态；下一轮会重试。")
                _alerted_error = code
            except Exception:
                logging.warning("Failure notification unavailable")
        raise
    finally:
        SCAN_LOCK.release()
