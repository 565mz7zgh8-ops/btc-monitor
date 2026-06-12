import os
import requests
import time

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

ALERT_PRICE = 110000
sent = False

while True:
    try:
        data = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
        ).json()

        price = float(data["price"])

        print("BTC:", price)

        if price >= ALERT_PRICE and not sent:
            requests.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                params={
                    "chat_id": CHAT_ID,
                    "text": f"🚀 BTC突破 {ALERT_PRICE}\n当前价格：{price}"
                }
            )
            sent = True

        time.sleep(60)

    except Exception as e:
        print(e)
        time.sleep(60)
