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
JOURNAL_FILE = "journal.json"

positions = {}
chat_id_global = None
journal = []

print("Exit Bot jalan dengan harga real + jurnal...")

def load_json_file(path, default_value):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except:
            return default_value
    return default_value

def save_json_file(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

def load_positions():
    global positions
    positions = load_json_file(POSITIONS_FILE, {})

def save_positions():
    save_json_file(POSITIONS_FILE, positions)

def load_chat():
    global chat_id_global
    data = load_json_file(CHAT_FILE, {})
    chat_id_global = data.get("chat_id")

def save_chat():
    global chat_id_global
    save_json_file(CHAT_FILE, {"chat_id": chat_id_global})

def load_journal():
    global journal
    journal = load_json_file(JOURNAL_FILE, [])

def save_journal():
    save_json_file(JOURNAL_FILE, journal)

def send_message(chat_id, text):
    requests.post(
        f"{URL}/sendMessage",
        json={"chat_id": chat_id, "text": text},
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

    if pos.get("pnl_pct") is not None:
        lines.append(f"PnL: {pos['pnl_pct']:+.2f}%")

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
        hist = ticker.history(period="1d", interval="15m")

        if hist is not None and not hist.empty:
            last_close = float(hist["Close"].dropna().iloc[-1])
            return round(last_close, 2)

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
        prev_signal = pos.get("last_signal")
        price, message = analyze_position(symbol, pos)

        if price is None:
            continue

        current_signal = pos.get("last_signal")

        if prev_signal != current_signal:
            send_message(chat_id_global, message)
            changed = True

    if changed:
        save_positions()

def append_journal(symbol, pos, close_price, close_reason="MANUAL CLOSE"):
    entry = float(pos["entry"])
    pnl_pct = ((close_price - entry) / entry) * 100.0

    item = {
        "symbol": symbol,
        "entry": round(entry, 2),
        "close": round(close_price, 2),
        "sl": pos.get("sl"),
        "tp1": pos.get("tp1"),
        "tp2": pos.get("tp2"),
        "last_signal": pos.get("last_signal"),
        "close_reason": close_reason,
        "pnl_pct": round(pnl_pct, 2)
    }
    journal.append(item)
    save_journal()

def handle_jurnal(chat_id):
    if not journal:
        send_message(chat_id, "Jurnal trading masih kosong.")
        return

    recent = journal[-10:]
    lines = ["JURNAL 10 TRADE TERAKHIR\n"]

    for i, item in enumerate(recent, start=1):
        lines.append(
            f"{i}. {item['symbol']}\n"
            f"Entry: {item['entry']:.2f}\n"
            f"Close: {item['close']:.2f}\n"
            f"PnL: {item['pnl_pct']:+.2f}%\n"
            f"Alasan tutup: {item['close_reason']}\n"
        )

    send_message(chat_id, "\n".join(lines))

def handle_rekap(chat_id):
    if not journal:
        send_message(chat_id, "Belum ada data jurnal untuk direkap.")
        return

    total = len(journal)
    wins = len([x for x in journal if x["pnl_pct"] > 0])
    losses = len([x for x in journal if x["pnl_pct"] <= 0])
    total_pnl = sum(x["pnl_pct"] for x in journal)
    avg_pnl = total_pnl / total if total else 0

    msg = (
        "REKAP TRADING\n\n"
        f"Total trade: {total}\n"
        f"Win: {wins}\n"
        f"Loss: {losses}\n"
        f"Total PnL: {total_pnl:+.2f}%\n"
        f"Rata-rata PnL: {avg_pnl:+.2f}%"
    )
    send_message(chat_id, msg)

def handle_command(chat_id, text):
    global chat_id_global

    parts = text.strip().split()

    if not parts:
        return

    cmd = parts[0].lower()

    if cmd == "/start":
        send_message(
            chat_id,
            "Exit Bot aktif (harga real Yahoo + jurnal).\n\n"
            "Command:\n"
            "/startpos KODE HARGA\n"
            "/setsl KODE HARGA\n"
            "/settp KODE TP1 [TP2]\n"
            "/status KODE\n"
            "/listpos\n"
            "/closepos KODE [HARGA_TUTUP]\n"
            "/jurnal\n"
            "/rekap"
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

        analyze_position(symbol, positions[symbol])
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
            send_message(chat_id, "Format: /closepos BRIS [2460]")
            return

        symbol = parts[1].upper()

        if symbol not in positions:
            send_message(chat_id, f"{symbol} tidak ditemukan.")
            return

        pos = positions[symbol]

        if len(parts) >= 3:
            try:
                close_price = float(parts[2])
            except:
                send_message(chat_id, "Harga penutupan tidak valid.")
                return
        else:
            close_price = pos.get("last_price")
            if close_price is None:
                close_price = get_real_price(symbol)
                if close_price is None:
                    send_message(chat_id, "Harga tutup tidak tersedia. Gunakan format: /closepos BRIS 2460")
                    return

        close_reason = pos.get("last_signal") or "MANUAL CLOSE"
        append_journal(symbol, pos, close_price, close_reason)
        del positions[symbol]
        save_positions()

        send_message(chat_id, f"{symbol} ditutup di {close_price:.2f}. Masuk ke jurnal trading.")
        return

    if cmd == "/jurnal":
        handle_jurnal(chat_id)
        return

    if cmd == "/rekap":
        handle_rekap(chat_id)
        return

    send_message(chat_id, "Perintah tidak dikenal.")

load_positions()
load_chat()
load_journal()

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

        if time.time() - last_check > 900:
            monitor_positions()
            last_check = time.time()

        time.sleep(2)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)