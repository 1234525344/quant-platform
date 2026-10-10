import base64
import json
import os

from fastapi import HTTPException
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from gmail_client import api
from mail_processor import scan

def authorized_push(auth_header):
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing identity")
    try:
        claims = id_token.verify_oauth2_token(
            auth_header[7:], Request(), audience=os.environ["PUBSUB_AUDIENCE"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid identity")
    if claims.get("email") != os.environ["PUBSUB_PUSH_SA_EMAIL"] or not claims.get("email_verified"):
        raise HTTPException(status_code=403, detail="Wrong service account")

def handle_notification(envelope, chat_id):
    try:
        payload = envelope["message"]["data"]
        decoded = base64.b64decode(payload, validate=True)
        event = json.loads(decoded)
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid event")
    if event.get("emailAddress", "").lower() != os.environ["MONITORED_GMAIL"].lower():
        raise HTTPException(status_code=403, detail="Wrong mailbox")
    if not chat_id:
        raise HTTPException(status_code=503, detail="Chat not configured")
    return scan(chat_id)

def start_watch():
    result = api().users().watch(userId="me", body={
        "topicName": os.environ["PUBSUB_TOPIC"],
        "labelIds": ["INBOX"],
        "labelFilterBehavior": "include",
    }).execute()
    return result.get("expiration")
