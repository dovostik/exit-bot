import requests
import time
import os
import random

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    print("TOKEN tidak ditemukan!")
    exit()

URL = f"https://api.telegram.org/bot{TOKEN}"
last_update_id = 0

positions = {}
chat_id_global = None

print("Exit Bot jalan...")

def send_message(chat_id, text):
    requests.post(f"{URL}/sendMessage", json={
        "chat_id": chat_id,
        "text": text
    })

def format_position(symbol, pos):
    lines = [
        f"{symbol}",
        f"Entry: {pos['entry']:.2f}",
        f"Status: {pos.get('status', 'dipantau')}",
    ]

    if pos.get("sl") is not None:
        lines.append(f"SL: {pos['sl']:.2f}")

    if pos.get("tp1") is not None:
        lines.append(f"TP1: {pos['tp1']:.2f}")

    if pos.get("tp2") is not None:
        lines.append(f"TP2: {pos['tp2']:.2f}")

    return "\n".join(lines)

def simulate_price(entry):
    change = random.uniform(-1.5, 1.5)
    return entry + change

def monitor_positions():
    global chat_id_global

    if not chat_id_global:
        return

    for symbol, pos in positions.items():
        entry = pos["entry"]
        price = simulate_price(entry)

        sl = pos.get("sl")
        tp1 = pos.get("tp1")

        message = f"{symbol}\nHarga sekarang: {price:.2f}\nEntry: {entry:.2f}\n"

        if sl and price <= sl:
            message += "❌ CUT FAST (kena SL)"
        elif tp1 and price >= tp1:
            message += "🎯 TAKE PROFIT tercapai"
        elif price > entry:
            message += "🟢 HOLD (masih profit)"
        else:
            message += "⚠️ WASPADA (mendekati SL)"

        send_message(chat_id_global, message)

def handle_command(chat_id, text):
    parts = text.strip().split()

    if not parts:
        return

    cmd = parts[0].lower()

    if cmd == "/start":
        send_message(
            chat_id,
            "Exit Bot aktif.\n\n"
            "Command:\n"
            "/startpos KODE HARGA\n"
            "/setsl KODE HARGA\n"
            "/settp KODE TP1 [TP2]\n"
            "/status KODE\n"
            "/listpos\n"
            "/closepos KODE"
        )
        return

    if cmd == "/startpos":
        if len(parts) < 3:
            send_message(chat_id, "Format: /startpos BRIS 2442")
            return

        symbol = parts[1].upper()

        try:
            entry = float(parts[2])
        except:
            send_message(chat_id, "Harga entry tidak valid.")
            return

        positions[symbol] = {
            "entry": entry,
            "sl": None,
            "tp1": None,
            "tp2": None,
            "status": "dipantau"
        }

        send_message(chat_id, "Posisi mulai dipantau.\n\n" + format_position(symbol, positions[symbol]))
        return

    if cmd == "/setsl":
        symbol = parts[1].upper()

        if symbol not in positions:
            send_message(chat_id, f"Posisi {symbol} belum ada.")
            return

        sl = float(parts[2])
        positions[symbol]["sl"] = sl

        send_message(chat_id, f"SL diatur.\n\n{format_position(symbol, positions[symbol])}")
        return

    if cmd == "/settp":
        symbol = parts[1].upper()

        if symbol not in positions:
            send_message(chat_id, f"Posisi {symbol} belum ada.")
            return

        tp1 = float(parts[2])
        tp2 = float(parts[3]) if len(parts) >= 4 else None

        positions[symbol]["tp1"] = tp1
        positions[symbol]["tp2"] = tp2

        send_message(chat_id, f"TP diatur.\n\n{format_position(symbol, positions[symbol])}")
        return

    if cmd == "/status":
        symbol = parts[1].upper()

        if symbol not in positions:
            send_message(chat_id, f"Posisi {symbol} belum ada.")
            return

        send_message(chat_id, format_position(symbol, positions[symbol]))
        return

    if cmd == "/listpos":
        if not positions:
            send_message(chat_id, "Belum ada posisi.")
            return

        text = "Posisi aktif:\n\n"
        for s, p in positions.items():
            text += format_position(s, p) + "\n\n"

        send_message(chat_id, text)
        return

    if cmd == "/closepos":
        symbol = parts[1].upper()

        if symbol in positions:
            del positions[symbol]
            send_message(chat_id, f"{symbol} ditutup.")
        else:
            send_message(chat_id, f"{symbol} tidak ditemukan.")
        return

    send_message(chat_id, "Perintah tidak dikenal.")

last_check = time.time()

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

                chat_id_global = chat_id

                handle_command(chat_id, text)

        if time.time() - last_check > 15:
            monitor_positions()
            last_check = time.time()

        time.sleep(2)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
