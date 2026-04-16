import requests
import time
import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    print("TOKEN tidak ditemukan!")
    exit()

URL = f"https://api.telegram.org/bot{TOKEN}"
last_update_id = 0

# simpan posisi sederhana di memori
positions = {}

print("Exit Bot jalan...")

def handle_command(chat_id, text):
    parts = text.strip().split()

    if text == "/start":
        send_message(chat_id, "Exit Bot aktif.\n\nCoba:\n/startpos BRIS 2442\n/status BRIS\n/closepos BRIS")
        return

    if parts[0] == "/startpos":
        if len(parts) < 3:
            send_message(chat_id, "Format: /startpos KODE HARGA\nContoh: /startpos BRIS 2442")
            return

        symbol = parts[1].upper()
        try:
            entry = float(parts[2])
        except:
            send_message(chat_id, "Harga entry tidak valid.")
            return

        positions[symbol] = {
            "entry": entry,
            "status": "dipantau"
        }

        send_message(
            chat_id,
            f"Posisi {symbol} mulai dipantau.\nEntry: {entry:.2f}\nStatus: dipantau"
        )
        return

    if parts[0] == "/status":
        if len(parts) < 2:
            send_message(chat_id, "Format: /status KODE\nContoh: /status BRIS")
            return

        symbol = parts[1].upper()
        if symbol not in positions:
            send_message(chat_id, f"Posisi {symbol} belum ada.")
            return

        pos = positions[symbol]
        send_message(
            chat_id,
            f"Status {symbol}\nEntry: {pos['entry']:.2f}\nStatus: {pos['status']}"
        )
        return

    if parts[0] == "/closepos":
        if len(parts) < 2:
            send_message(chat_id, "Format: /closepos KODE\nContoh: /closepos BRIS")
            return

        symbol = parts[1].upper()
        if symbol in positions:
            del positions[symbol]
            send_message(chat_id, f"Posisi {symbol} ditutup. Monitoring dihentikan.")
        else:
            send_message(chat_id, f"Posisi {symbol} tidak ditemukan.")
        return

    send_message(chat_id, f"Perintah belum dikenal.\nKamu kirim: {text}")

def send_message(chat_id, text):
    requests.post(f"{URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

while True:
    try:
        res = requests.get(
            f"{URL}/getUpdates",
            params={"offset": last_update_id + 1}
        ).json()

        for update in res.get("result", []):
            last_update_id = update["update_id"]

            if "message" in update:
                chat_id = update["message"]["chat"]["id"]
                text = update["message"].get("text", "")
                print("Pesan masuk:", text)
                handle_command(chat_id, text)

        time.sleep(2)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
