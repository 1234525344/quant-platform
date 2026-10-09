import os
import httpx

def send_message(chat_id: str, text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    endpoint = "https://api.telegram.org/bot" + token + "/sendMessage"
    response = httpx.post(endpoint, json={"chat_id": chat_id, "text": text[:3900]}, timeout=15)
    if response.status_code != 200:
        raise RuntimeError("Telegram send failed (HTTP " + str(response.status_code) + ")")
    if not response.json().get("ok"):
        raise RuntimeError("Telegram delivery rejected")
