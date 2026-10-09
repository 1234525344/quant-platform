import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

def api():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)

def processed_label(gmail):
    labels = gmail.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label["name"] == "BROKER_ALERTS_SENT":
            return label["id"]
    return gmail.users().labels().create(userId="me", body={
        "name": "BROKER_ALERTS_SENT",
        "labelListVisibility": "labelHide",
        "messageListVisibility": "hide",
    }).execute()["id"]
