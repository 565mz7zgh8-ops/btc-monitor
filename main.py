import os
import time
import traceback
import requests
import pandas as pd
import numpy as np
import yfinance as yf

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": msg
            },
            timeout=20
        )
    except Exception as e:
        print("Telegram发送失败:", e)


def get_klines():
    try:
        df = yf.download(
            "BTC-USD",
            interval="1h",
            period="7d",
            progress=False,
            auto_adjust=False
        )

        if df.empty:
            raise Exception("Yahoo返回空数据")

        df = df.rename(columns=str.lower)

        return df

    except Exception as e:
        print("获取行情失败:", e)
        raise


def calc_macd(df, fast=12, slow=26, signal=9):
    ema_fast = df["close"].ewm(span=fast).mean()
    ema_slow = df["close"].ewm(span=slow).mean()

    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal).mean()

    return float(macd.iloc[-1] - sig.iloc[-1])


def calc_cmf(df, period=20):
    mfm = (
        ((df["close"] - df["low"]) -
         (df["high"] - df["close"]))
        /
        (df["high"] - df["low"])
    )

    mfm = mfm.replace([np.inf, -np.inf], 0).fillna(0)

    mfv = mfm * df["volume"]

    cmf = (
        mfv.rolling(period).sum()
        /
        df["volume"].rolling(period).sum()
    ).iloc[-1]

    return float(cmf)


def calc_obv_trend(df, n=10):
    direction = np.sign(df["close"].diff()).fillna(0)

    obv = (direction * df["volume"]).cumsum()

    return float(obv.iloc[-1] - obv.iloc[-n])


def calc_volatility(df, n=20):
    returns = df["close"].pct_change()

    return float(
        returns.rolling(n).std().iloc[-1] * 100
    )


def describe_market():

    df = get_klines()

    if len(df) < 30:
        return "⚠️ K线数据不足"

    price = float(df["close"].iloc[-1])

    macd_hist = calc_macd(df)
    cmf = calc_cmf(df)
    obv_trend = calc_obv_trend(df)
    vol = calc_volatility(df)

    macd_desc = "📈 多头占优" if macd_hist > 0 else "📉 空头占优"

    if cmf > 0.1:
        cmf_desc = f"资金流入 ({cmf:.2f})"
    elif cmf < -0.1:
        cmf_desc = f"资金流出 ({cmf:.2f})"
    else:
        cmf_desc = f"资金中性 ({cmf:.2f})"

    price_trend = float(
        df["close"].iloc[-1] - df["close"].iloc[-10]
    )

    if (price_trend > 0 and obv_trend > 0) or \
       (price_trend < 0 and obv_trend < 0):
        obv_desc = "量价同步"
    else:
        obv_desc = "量价背离"

    if vol < 0.3:
        vol_desc = f"低波动 ({vol:.2f}%)"
    elif vol < 0.8:
        vol_desc = f"中波动 ({vol:.2f}%)"
    else:
        vol_desc = f"高波动 ({vol:.2f}%)"

    return (
        f"📊 BTC 市场状态\n\n"
        f"💰 价格: {price:,.0f} USD\n"
        f"📈 趋势: {macd_desc}\n"
        f"💵 资金流: {cmf_desc}\n"
        f"📦 OBV: {obv_desc}\n"
        f"🌊 波动率: {vol_desc}"
    )


def main_loop():

    send_telegram("🚀 BTC监控机器人启动成功")

    while True:

        try:
            msg = describe_market()
            send_telegram(msg)

        except Exception:
            send_telegram(
                "⚠️ 程序异常\n\n"
                + traceback.format_exc()[:3000]
            )

        time.sleep(3600)


if __name__ == "__main__":
    main_loop()
