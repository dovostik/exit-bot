import requests
import time
import os
import json
import yfinance as yf

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    print("TOKEN tidak ditemukan!")
    exit()

URL = f"https://api.telegram.org/bot{TOKEN}"
last_update_id = 0

POSITIONS_FILE = "positions.json"
CHAT_FILE = "chat.json"

positions = {}
chat_id_global = None

print("Exit Bot jalan dengan harga real...")


def load_positions():
    global positions
    if os.path.exists(POSITIONS_FILE):
        try:
            with open(POSITIONS_FILE, "r") as f:
                positions = json.load(f)
        except:
            positions = {}
    else:
        positions = {}


def save_positions():
    with open(POSITIONS_FILE, "w") as f:
        json.dump(positions, f)


def load_chat():
    global chat_id_global
    if os.path.exists(CHAT_FILE):
        try:
            with open(CHAT_FILE, "r") as f:
                data = json.load(f)
                chat_id_global = data.get("chat_id")
        except:
            chat_id_global = None
    else:
        chat_id_global = None


def save_chat():
    global chat_id_global
    with open(CHAT_FILE, "w") as f:
        json.dump({"chat_id": chat_id_global}, f)


def send_message(chat_id, text):
    requests.post(
        f"{URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
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

    if pos.get("last_price") is not None:
        lines.append(f"Harga terakhir: {pos['last_price']:.2f}")

    if pos.get("last_signal") is not None:
        lines.append(f"Rekomendasi: {pos['last_signal']}")

    return "\n".join(lines)


def yahoo_symbol(symbol):
    symbol = symbol.upper().strip()
    if symbol.endswith(".JK"):
        return symbol
    return f"{symbol}.JK"


def get_real_price(symbol):
    ys = yahoo_symbol(symbol)

    try:
        ticker = yf.Ticker(ys)

        # coba ambil data intraday 15m dulu
        hist = ticker.history(period="1d", interval="15m")

        if hist is not None and not hist.empty:
            last_close = float(hist["Close"].dropna().iloc[-1])
            return round(last_close, 2)

        # fallback ke daily
        hist = ticker.history(period="5d", interval="1d")
        if hist is not None and not hist.empty:
            last_close = float(hist["Close"].dropna().iloc[-1])
            return round(last_close, 2)

    except Exception as e:
        print("Yahoo error:", symbol, e)

    return None


def analyze_position(symbol, pos):
    entry = pos["entry"]
    price = get_real_price(symbol)

    if price is None:
        return None, "Data harga belum tersedia."

    sl = pos.get("sl")
    tp1 = pos.get("tp1")
    tp2 = pos.get("tp2")

    pos["last_price"] = price

    pnl_pct = ((price - entry) / entry) * 100
    pos["pnl_pct"] = round(pnl_pct, 2)

    if pos.get("max_profit_pct") is None:
        pos["max_profit_pct"] = pos["pnl_pct"]
    else:
        pos["max_profit_pct"] = max(pos["max_profit_pct"], pos["pnl_pct"])

    max_profit = pos.get("max_profit_pct", 0)

    giveback_ratio = 0
    if max_profit > 0:
        giveback_ratio = (max_profit - pnl_pct) / max_profit
        if giveback_ratio < 0:
            giveback_ratio = 0

    pos["giveback_ratio"] = round(giveback_ratio, 2)

    signal = ""
    action = ""
    prev_signal = pos.get("last_signal")

    if sl is not None and price <= sl:
        signal = "❌ CUT FAST"
        action = "Harga sudah di bawah/menyentuh SL."
    elif tp2 is not None and price >= tp2:
        signal = "🏁 TAKE PROFIT FULL"
        action = "Harga sudah mencapai TP2."
    elif tp1 is not None and price >= tp1:
        signal = "🎯 TAKE PROFIT PARTIAL"
        action = "Harga sudah mencapai TP1."
    elif max_profit >= 1.0 and giveback_ratio >= 0.5:
        signal = "🚨 FAILURE EXIT"
        action = "Sempat profit bagus, tapi giveback sudah besar."
    elif max_profit >= 0.8 and pnl_pct > 0:
        signal = "🛡 PROTECT PROFIT"
        action = "Profit ada, amankan posisi / naikkan SL."
    elif price > entry:
        signal = "🟢 HOLD"
        action = "Masih di atas harga entry."
    else:
        signal = "⚠️ WASPADA"
        action = "Belum aman, dekat area entry / risiko."

    pos["last_signal"] = signal

    message = (
        f"{symbol}\n"
        f"Harga sekarang: {price:.2f}\n"
        f"Entry: {entry:.2f}\n"
        f"PnL: {pnl_pct:+.2f}%\n"
        f"Max Profit: {max_profit:+.2f}%\n"
        f"Giveback: {giveback_ratio:.0%}\n\n"
        f"{signal}\n"
        f"{action}"
    )

    return price, message


def monitor_positions():
    global chat_id_global

    if not chat_id_global:
        return

    changed = False

    for symbol, pos in positions.items():
        entry = pos["entry"]
        price, message = analyze_position(symbol, pos)

        if price is None:
            continue
            
            current_signal = pos.get("last_signal")

        # hanya kirim jika sinyal berubah
        if prev_signal != current_signal:
            send_message(chat_id_global, message)
            changed = True

    if changed:
        save_positions()


def handle_command(chat_id, text):
    global chat_id_global

    parts = text.strip().split()

    if not parts:
        return

    cmd = parts[0].lower()

    if cmd == "/start":
        send_message(
            chat_id,
            "Exit Bot aktif (harga real Yahoo).\n\n"
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
            "status": "dipantau",
            "last_price": None,
            "last_signal": None,
            "pnl_pct": None,
            "max_profit_pct": 0,
            "giveback_ratio": 0
        }

        save_positions()
        send_message(chat_id, "Posisi mulai dipantau.\n\n" + format_position(symbol, positions[symbol]))
        return

    if cmd == "/setsl":
        if len(parts) < 3:
            send_message(chat_id, "Format: /setsl BRIS 2432")
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
        save_positions()

        send_message(chat_id, f"SL diatur.\n\n{format_position(symbol, positions[symbol])}")
        return

    if cmd == "/settp":
        if len(parts) < 3:
            send_message(chat_id, "Format: /settp BRIS 2480 [2510]")
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
        save_positions()

        send_message(chat_id, f"TP diatur.\n\n{format_position(symbol, positions[symbol])}")
        return

    if cmd == "/status":
        if len(parts) < 2:
            send_message(chat_id, "Format: /status BRIS")
            return

        symbol = parts[1].upper()

        if symbol not in positions:
            send_message(chat_id, f"Posisi {symbol} belum ada.")
            return

        price, _ = analyze_position(symbol, positions[symbol])
        save_positions()
        send_message(chat_id, format_position(symbol, positions[symbol]))
        return

    if cmd == "/listpos":
        if not positions:
            send_message(chat_id, "Belum ada posisi.")
            return

        text_out = "Posisi aktif:\n\n"
        for symbol, pos in positions.items():
            text_out += format_position(symbol, pos) + "\n\n"

        send_message(chat_id, text_out)
        return

    if cmd == "/closepos":
        if len(parts) < 2:
            send_message(chat_id, "Format: /closepos BRIS")
            return

        symbol = parts[1].upper()

        if symbol in positions:
            del positions[symbol]
            save_positions()
            send_message(chat_id, f"{symbol} ditutup.")
        else:
            send_message(chat_id, f"{symbol} tidak ditemukan.")
        return

    send_message(chat_id, "Perintah tidak dikenal.")


load_positions()
load_chat()

last_check = time.time()

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

                chat_id_global = chat_id
                save_chat()

                handle_command(chat_id, text)

        # interval monitor sementara tetap 900 detik dulu
        if time.time() - last_check > 900:
            monitor_positions()
            last_check = time.time()

        time.sleep(2)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
