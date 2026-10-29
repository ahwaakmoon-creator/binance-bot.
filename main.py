# -*- coding: utf-8 -*-
import requests
import time
import threading
from datetime import datetime

# ==== التوكن حق بوت بينانس ====
BOT_TOKEN = "8621413631:AAHz74PuXHuY6pYIl2bunPa6vflXIwm3scQ"
CHAT_ID = "5739750013"

CRYPTO_MARKETS = {
    "BTCUSDT": "₿ BTC",
    "ETHUSDT": "Ξ ETH",
    "SOLUSDT": "◎ SOL",
    "BNBUSDT": "Ⓞ BNB",
    "XRPUSDT": "✕ XRP",
}
FOREX_MARKETS = {
    "XAUUSDT": "🥇 Gold",
    "EURUSDT": "🇪🇺 EUR",
    "GBPUSDT": "🇬🇧 GBP",
}

current_watchlist = {}

def fetch(symbol, interval="5m", limit=250):
    try:
        url = "https://fapi.binance.com/fapi/v1/klines"
        r = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=10)
        if r.status_code != 200: return None
        d = r.json()
        if not d: return None
        return {
            "c": [float(k[4]) for k in d], 
            "h": [float(k[2]) for k in d], 
            "l": [float(k[3]) for k in d]
        }
    except Exception:
        return None

def calc_ema(data, period):
    k = 2 / (period + 1)
    ema = data[0]
    for price in data[1:]: ema = price * k + ema * (1 - k)
    return ema

def calc_bollinger(data, period=20, std_dev=2):
    if len(data) < period: return None, None, None
    sma = sum(data[-period:]) / period
    variance = sum((x - sma) ** 2 for x in data[-period:]) / period
    std = variance ** 0.5
    return sma + (std * std_dev), sma, sma - (std * std_dev)

def calc_atr(h, l, c, period=14):
    trs = [max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(1, len(c))]
    return sum(trs[-period:]) / period

def send_telegram(msg, reply_markup=None):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
        if reply_markup: payload["reply_markup"] = reply_markup
        requests.post(url, data=payload, timeout=10)
    except Exception:
        pass

def handle_commands():
    global current_watchlist
    last_id = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            resp = requests.get(url, params={"offset": last_id + 1, "timeout": 30}, timeout=35)
            if resp.status_code == 200:
                data = resp.json()
                for update in data.get("result", []):
                    last_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].strip()
                        if text == "/start":
                            keyboard = {
                                "keyboard": [
                                    [{"text": "🪙 عملات كريبتو"}, {"text": "💱 فوركس وذهب"}],
                                    [{"text": "🛑 إيقاف المراقبة"}]
                                ],
                                "resize_keyboard": True,
                                "one_time_keyboard": False
                            }
                            send_telegram("🖤🧠 <b>مرحباً بك في بوت إشارات بينانس.</b>\n\nاختر السوق اللي تبي تراقبه:", reply_markup=keyboard)
                        elif text == "🪙 عملات كريبتو":
                            current_watchlist = CRYPTO_MARKETS
                            send_telegram("✅ <b>تم تفعيل مراقبة الكريبتو.</b>")
                        elif text == "💱 فوركس وذهب":
                            current_watchlist = FOREX_MARKETS
                            send_telegram("✅ <b>تم تفعيل مراقبة الفوركس والذهب.</b>")
                        elif text == "🛑 إيقاف المراقبة":
                            current_watchlist = {}
                            send_telegram("🛑 <b>تم إيقاف المراقبة.</b>")
        except Exception as e:
            print(f"Network Error: {e}")
        time.sleep(1)

def scanner():
    last_signal_time = {}
    while True:
        try:
            if not current_watchlist:
                time.sleep(5)
                continue

            current_sec = int(time.time()) % 300
            if current_sec < 290:
                time.sleep(5)
                continue

            for symbol, name in current_watchlist.items():
                data = fetch(symbol)
                if not data or len(data["c"]) < 200: continue

                closes = data["c"]
                highs = data["h"]
                lows = data["l"]
                current_price = closes[-1]
                
                ema200 = calc_ema(closes[-200:], 200)
                upper, mid, lower = calc_bollinger(closes[-20:])
                atr = calc_atr(highs, lows, closes)

                if not ema200 or not upper or not atr: continue

                signal = None
                sl = 0
                tp = 0

                if current_price > ema200 and closes[-2] <= upper and current_price > upper:
                    signal = "🟢 <b>شراء (LONG)</b>"
                    sl = current_price - (atr * 1.5)
                    tp = current_price + (atr * 3.0)
                elif current_price < ema200 and closes[-2] >= lower and current_price < lower:
                    signal = "🔴 <b>بيع (SHORT)</b>"
                    sl = current_price + (atr * 1.5)
                    tp = current_price - (atr * 3.0)

                if signal:
                    now = time.time()
                    if symbol in last_signal_time and now - last_signal_time[symbol] < 900:
                        continue
                    last_signal_time[symbol] = now
                    
                    price_str = f"{current_price:.4f}" if current_price < 10 else f"{current_price:.2f}"
                    sl_str = f"{sl:.4f}" if sl < 10 else f"{sl:.2f}"
                    tp_str = f"{tp:.4f}" if tp < 10 else f"{tp:.2f}"

                    msg = f"🖤🧠 <b>Futures Signal</b>\n\n"
                    msg += f"📊 الزوج: <b>{name}</b>\n"
                    msg += f"💰 سعر الدخول: <code>{price_str}</code>\n"
                    msg += f"🛑 وقف الخسارة (SL): <code>{sl_str}</code>\n"
                    msg += f"🎯 الهدف (TP): <code>{tp_str}</code>\n\n"
                    msg += f"{signal}\n"
                    msg += f"⚖️ <i>استخدم رافعة 5x أو 10x</i>"
                    
                    send_telegram(msg)
                    time.sleep(2)
        except Exception:
            pass
        time.sleep(10)

if __name__ == "__main__":
    try:
        print("Deleting Webhook...")
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook")
        print("Webhook Deleted. Starting polling...")
    except:
        pass
        
    send_telegram("🖤🧠 <b>بوت إشارات Binance Futures جاهز.</b>\nاكتب /start لاختيار السوق.")
    threading.Thread(target=handle_commands, daemon=True).start()
    threading.Thread(target=scanner, daemon=True).start()
    
    while True:
        time.sleep(60)
