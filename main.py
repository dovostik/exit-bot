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
    requests.post(f"{URL}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=30)

def yahoo_symbol(symbol):
    symbol = symbol.upper().strip()
    return symbol if symbol.endswith(".JK") else f"{symbol}.JK"

def get_real_price(symbol):
    ys = yahoo_symbol(symbol)
    try:
        ticker = yf.Ticker(ys)
        hist = ticker.history(period="1d", interval="15m")
        if hist is not None and not hist.empty:
            return round(float(hist["Close"].dropna().iloc[-1]), 2)
    except:
        pass
    return None

def analyze_position(symbol, pos):
    entry = pos["entry"]
    price = get_real_price(symbol)
    if price is None:
        return None, "Data harga belum tersedia."

    pos["last_price"] = price
    pnl_pct = ((price - entry) / entry) * 100
    pos["pnl_pct"] = round(pnl_pct, 2)

    if pos.get("max_profit_pct") is None:
        pos["max_profit_pct"] = pos["pnl_pct"]
    else:
        pos["max_profit_pct"] = max(pos["max_profit_pct"], pos["pnl_pct"])

    signal = "🟢 HOLD" if price > entry else "⚠️ WASPADA"
    pos["last_signal"] = signal

    message = f"{symbol}\nHarga: {price}\nEntry: {entry}\n{signal}"
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

load_positions()
load_chat()

last_check = time.time()

while True:
    try:
        res = requests.get(f"{URL}/getUpdates", params={"offset": last_update_id + 1}).json()

        for update in res.get("result", []):
            last_update_id = update["update_id"]

            if "message" in update:
                chat_id = update["message"]["chat"]["id"]
                chat_id_global = chat_id
                save_chat()

        if time.time() - last_check > 900:
            monitor_positions()
            last_check = time.time()

        time.sleep(2)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
