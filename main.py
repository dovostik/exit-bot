import requests
import time
import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
URL = f"https://api.telegram.org/bot{TOKEN}"

last_update_id = None

print("Bot Telegram jalan...")

while True:
    try:
        res = requests.get(f"{URL}/getUpdates").json()

        for update in res["result"]:
            update_id = update["update_id"]

            if last_update_id is not None and update_id <= last_update_id:
                continue

            last_update_id = update_id

            if "message" in update:
                chat_id = update["message"]["chat"]["id"]
                text = update["message"].get("text", "")

                reply = f"Kamu kirim: {text}"

                requests.post(f"{URL}/sendMessage", json={
                    "chat_id": chat_id,
                    "text": reply
                })

        time.sleep(2)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
