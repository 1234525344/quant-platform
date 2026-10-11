# -*- coding: utf-8 -*-
import base64
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app
import mail_processor as processor
import polling


class Result:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class Gmail:
    def __init__(self, count=0, ready=True):
        self.data = {str(i): self.message() for i in range(count)}
        self.names = [{"name": "BROKER_ALERTS_SENT", "id": "sent"}]
        if ready:
            self.names.append({"name": polling.BASELINE_LABEL, "id": "ready"})
        self.queries = []
        self.page_reads = 0
        self.modifications = []
        self.modify_failure = False

    @staticmethod
    def message(sender="cs@gigamoney.com", subject="Account update"):
        return {"labelIds": [], "payload": {
            "headers": [{"name": "From", "value": sender}, {"name": "Subject", "value": subject}],
            "mimeType": "text/plain", "body": {"data": base64.urlsafe_b64encode(b"Fixture body").decode()}}}

    def users(self): return self
    def messages(self): self.resource = "messages"; return self
    def labels(self): self.resource = "labels"; return self
    def getProfile(self, **kwargs): return Result({"emailAddress": "owner@example.com"})

    def list(self, **kwargs):
        if self.resource == "labels":
            return Result({"labels": self.names.copy()})
        self.queries.append(kwargs["q"])
        self.page_reads += 1
        candidates = [i for i, msg in self.data.items() if "sent" not in msg["labelIds"]]
        offset = int(kwargs.get("pageToken", "0"))
        page = {"messages": [{"id": i} for i in candidates[offset:offset + 100]]}
        if offset + 100 < len(candidates):
            page["nextPageToken"] = str(offset + 100)
        return Result(page)

    def get(self, id, **kwargs): return Result(self.data[id])

    def modify(self, id, **kwargs):
        if self.modify_failure:
            raise RuntimeError("fixture label failure")
        self.data[id]["labelIds"].append("sent")
        self.modifications.append(id)
        return Result({})

    def create(self, body, **kwargs):
        self.names.append({"name": body["name"], "id": "ready"})
        return Result({"id": "ready"})


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    monkeypatch.setenv("MONITORED_GMAIL", "owner@example.com")
    monkeypatch.setenv("POLL_SECRET", "fixture-secret")
    monkeypatch.setenv("POLL_BASELINE_BEFORE", "1791700000")
    monkeypatch.delenv("AI_ANALYSIS_ENABLED", raising=False)
    monkeypatch.delenv("BROKER_SENDER_ALLOWLIST", raising=False)
    monkeypatch.setattr(app, "CHAT_ID", "fixture-chat")
    monkeypatch.setattr(polling, "_alerted_error", None)
    polling.STATE.update(status="not_started", baseline_ready=None, last_result=None, error_code=None)


@pytest.mark.parametrize("headers", [{}, {"X-Poll-Secret": "wrong"}])
def test_auth_rejects_before_gmail(monkeypatch, headers):
    monkeypatch.setattr(app, "run_poll", lambda *a, **k: pytest.fail("unauthorized scan"))
    assert TestClient(app.app).post("/admin/poll", headers=headers).status_code == 401


def test_unconfigured_secret_rejects(monkeypatch):
    monkeypatch.delenv("POLL_SECRET")
    assert TestClient(app.app).post("/admin/poll", headers={"X-Poll-Secret": "fixture-secret"}).status_code == 401


def test_pagination_then_dedupe(monkeypatch):
    gmail = Gmail(205)
    delivered = []
    monkeypatch.setattr(polling, "api", lambda: gmail)
    monkeypatch.setattr(processor, "send_message", lambda *args: delivered.append(args))
    first = polling.run_poll("fixture-chat")
    assert first["sent"] == first["marked"] == 205
    assert gmail.page_reads == 3
    assert all("-label:BROKER_ALERTS_SENT" in query for query in gmail.queries)
    assert polling.run_poll("fixture-chat")["sent"] == 0
    assert len(delivered) == 205


def test_automatic_reply_and_exact_sender_filter(monkeypatch):
    gmail = Gmail(3)
    gmail.data["0"] = Gmail.message(subject="Automatic Reply: inquiry")
    gmail.data["1"] = Gmail.message(sender="attacker@example.com")
    delivered = []
    monkeypatch.setattr(processor, "send_message", lambda *args: delivered.append(args))
    result = processor.scan_stats(gmail, "fixture-chat")
    assert result == {"examined": 3, "sent": 1, "marked": 2, "automatic": 1}
    assert gmail.data["1"]["labelIds"] == []
    assert len(delivered) == 1


def test_send_failure_retry_and_alert_suppression(monkeypatch):
    gmail = Gmail(1)
    alerts = []
    monkeypatch.setattr(polling, "api", lambda: gmail)
    monkeypatch.setattr(processor, "send_message", lambda *a: (_ for _ in ()).throw(RuntimeError("fixture")))
    monkeypatch.setattr(polling, "send_message", lambda *args: alerts.append(args))
    for _ in range(2):
        with pytest.raises(RuntimeError): polling.run_poll("fixture-chat")
    assert gmail.modifications == []
    assert len(alerts) == 1
    monkeypatch.setattr(processor, "send_message", lambda *a: None)
    assert polling.run_poll("fixture-chat")["sent"] == 1
    assert len(alerts) == 2  # One failure, one recovery.


def test_baseline_is_durable_and_idempotent(monkeypatch):
    gmail = Gmail(2, ready=False)
    monkeypatch.setattr(polling, "api", lambda: gmail)
    monkeypatch.setattr(processor, "send_message", lambda *a: pytest.fail("old email flood"))
    with pytest.raises(polling.BaselineRequired): polling.run_poll("fixture-chat")
    assert polling.run_poll("fixture-chat", bootstrap=True)["marked"] == 2
    assert "before:1791700000" in gmail.queries[-1]
    gmail.data["new"] = Gmail.message()
    assert polling.run_poll("fixture-chat", bootstrap=True)["marked"] == 0
    assert gmail.data["new"]["labelIds"] == []


def test_baseline_failure_cannot_create_ready_marker(monkeypatch):
    gmail = Gmail(1, ready=False)
    gmail.modify_failure = True
    monkeypatch.setattr(polling, "api", lambda: gmail)
    monkeypatch.setattr(polling, "send_message", lambda *a: None)
    with pytest.raises(RuntimeError): polling.run_poll("fixture-chat", bootstrap=True)
    assert not any(item["name"] == polling.BASELINE_LABEL for item in gmail.names)


def test_lock_shared_with_legacy_scan():
    processor.SCAN_LOCK.acquire()
    try:
        with pytest.raises(processor.ScanBusy): polling.run_poll("fixture-chat")
        with pytest.raises(processor.ScanBusy): processor.scan("fixture-chat")
        response = TestClient(app.app).post("/admin/poll", headers={"X-Poll-Secret": "fixture-secret"})
        assert response.status_code == 409
    finally:
        processor.SCAN_LOCK.release()


def test_failure_response_does_not_leak_details(monkeypatch):
    def fail(*args, **kwargs): raise RuntimeError("private email body / credential")
    monkeypatch.setattr(app, "run_poll", fail)
    response = TestClient(app.app).post("/admin/poll", headers={"X-Poll-Secret": "fixture-secret"})
    assert response.status_code == 503
    assert "private" not in response.text


def test_wrong_mailbox_cannot_scan(monkeypatch):
    gmail = Gmail(1)
    monkeypatch.setenv("MONITORED_GMAIL", "another@example.com")
    monkeypatch.setattr(polling, "api", lambda: gmail)
    monkeypatch.setattr(polling, "send_message", lambda *a: None)
    with pytest.raises(ValueError): polling.run_poll("fixture-chat")
    assert gmail.page_reads == 0
