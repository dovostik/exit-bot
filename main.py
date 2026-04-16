import requests
import time
import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    print("TOKEN tidak ditemukan!")
    exit()

URL = f"https://api.telegram.org/bot{TOKEN}"
last_update_id = 0

# penyimpanan sementara di memori
positions = {}

print("Exit Bot jalan...")

def send_message(chat_id, text):
    requests.post(
        f"{URL}/sendMessage",
        json={"chat_id": chat_id, "text": text}
    )

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

def handle_start(chat_id):
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

def handle_startpos(chat_id, parts):
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
        "sl": None,
        "tp1": None,
        "tp2": None,
        "status": "dipantau"
    }

    send_message(
        chat_id,
        "Posisi mulai dipantau.\n\n" + format_position(symbol, positions[symbol])
    )

def handle_setsl(chat_id, parts):
    if len(parts) < 3:
        send_message(chat_id, "Format: /setsl KODE HARGA\nContoh: /setsl BRIS 2432")
        return

    symbol = parts[1].upper()

    if symbol not in positions:
        send_message(chat_id, f"Posisi {symbol} belum ada.")
        return

    try:
        sl = float(parts[2])
    except:
        send_message(chat_id, "Harga SL tidak valid.")
        return

    positions[symbol]["sl"] = sl

    send_message(
        chat_id,
        f"SL berhasil diatur.\n\n{format_position(symbol, positions[symbol])}"
    )

def handle_settp(chat_id, parts):
    if len(parts) < 3:
        send_message(chat_id, "Format: /settp KODE TP1 [TP2]\nContoh: /settp BRIS 2480 2510")
        return

    symbol = parts[1].upper()

    if symbol not in positions:
        send_message(chat_id, f"Posisi {symbol} belum ada.")
        return

    try:
        tp1 = float(parts[2])
    except:
        send_message(chat_id, "TP1 tidak valid.")
        return

    tp2 = None
    if len(parts) >= 4:
        try:
            tp2 = float(parts[3])
        except:
            send_message(chat_id, "TP2 tidak valid.")
            return

    positions[symbol]["tp1"] = tp1
    positions[symbol]["tp2"] = tp2

    send_message(
        chat_id,
        f"Target profit berhasil diatur.\n\n{format_position(symbol, positions[symbol])}"
    )

def handle_status(chat_id, parts):
    if len(parts) < 2:
        send_message(chat_id, "Format: /status KODE\nContoh: /status BRIS")
        return

    symbol = parts[1].upper()

    if symbol not in positions:
        send_message(chat_id, f"Posisi {symbol} belum ada.")
        return

    send_message(chat_id, "Status posisi:\n\n" + format_position(symbol, positions[symbol]))

def handle_listpos(chat_id):
    if not positions:
        send_message(chat_id, "Belum ada posisi yang dipantau.")
        return

    lines = ["Daftar posisi aktif:\n"]
    for symbol, pos in positions.items():
        line = f"- {symbol} | Entry {pos['entry']:.2f}"
        if pos.get("sl") is not None:
            line += f" | SL {pos['sl']:.2f}"
        if pos.get("tp1") is not None:
            line += f" | TP1 {pos['tp1']:.2f}"
        lines.append(line)

    send_message(chat_id, "\n".join(lines))

def handle_closepos(chat_id, parts):
    if len(parts) < 2:
        send_message(chat_id, "Format: /closepos KODE\nContoh: /closepos BRIS")
        return

    symbol = parts[1].upper()

    if symbol in positions:
        del positions[symbol]
        send_message(chat_id, f"Posisi {symbol} ditutup. Monitoring dihentikan.")
    else:
        send_message(chat_id, f"Posisi {symbol} tidak ditemukan.")

def handle_command(chat_id, text):
    parts = text.strip().split()

    if not parts:
        return

    cmd = parts[0].lower()

    if cmd == "/start":
        handle_start(chat_id)
        return

    if cmd == "/startpos":
        handle_startpos(chat_id, parts)
        return

    if cmd == "/setsl":
        handle_setsl(chat_id, parts)
        return

    if cmd == "/settp":
        handle_settp(chat_id, parts)
        return

    if cmd == "/status":
        handle_status(chat_id, parts)
        return

    if cmd == "/listpos":
        handle_listpos(chat_id)
        return

    if cmd == "/closepos":
        handle_closepos(chat_id, parts)
        return

    send_message(chat_id, "Perintah belum dikenal.\nGunakan /start untuk melihat command.")

while True:
    try:
        res = requests.get(
            f"{URL}/getUpdates",
            params={"offset": last_update_id + 1},
            timeout=30
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
