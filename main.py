import os
import time
import requests
import traceback
import pandas as pd
import numpy as np

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


def send_telegram(msg):
    try:
        if not BOT_TOKEN:
            print("BOT_TOKEN 未设置")
            return

        if not CHAT_ID:
            print("CHAT_ID 未设置")
            return

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


def get_klines(symbol="BTCUSDT", interval="1h", limit=100):
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/klines",
            params={
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            },
            timeout=20
        )

        print("状态码:", r.status_code)
        print("返回内容:", r.text[:500])

        data = r.json()

        if not isinstance(data, list):
            raise Exception(f"Binance异常返回: {data}")

        if len(data) == 0:
            raise Exception("Binance返回空数据")

        df = pd.DataFrame(
            data,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "qav",
                "trades",
                "taker_base",
                "taker_quote",
                "ignore"
            ]
        )

        for c in ["open", "high", "low", "close", "volume"]:
            df[c] = df[c].astype(float)

        return df

    except Exception as e:
        print("获取K线失败:", e)
        raise


def calc_macd(df, fast=12, slow=26, signal=9):
    ema_fast = df["close"].ewm(span=fast).mean()
    ema_slow = df["close"].ewm(span=slow).mean()

    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal).mean()

    return macd.iloc[-1] - sig.iloc[-1]


def calc_cmf(df, period=20):
    mfm = (
        ((df["close"] - df["low"]) -
         (df["high"] - df["close"]))
        /
        (df["high"] - df["low"])
    )

    mfm = mfm.replace([np.inf, -np.inf], 0).fillna(0)

    mfv = mfm * df["volume"]

    return (
        mfv.rolling(period).sum()
        /
        df["volume"].rolling(period).sum()
    ).iloc[-1]


def calc_obv_trend(df, n=10):
    direction = np.sign(df["close"].diff()).fillna(0)

    obv = (direction * df["volume"]).cumsum()

    return obv.iloc[-1] - obv.iloc[-n]


def calc_volatility(df, n=20):
    returns = df["close"].pct_change()

    return returns.rolling(n).std().iloc[-1] * 100


def describe_market():
    df = get_klines()

    if df.empty:
        return "⚠️ Binance返回空K线"

    price = df["close"].iloc[-1]

    macd_hist = calc_macd(df)
    cmf = calc_cmf(df)
    obv_trend = calc_obv_trend(df)
    vol = calc_volatility(df)

    macd_desc = "短期上行" if macd_hist > 0 else "短期下行"

    if cmf > 0.1:
        cmf_desc = f"流入 (CMF {cmf:.2f})"
    elif cmf < -0.1:
        cmf_desc = f"流出 (CMF {cmf:.2f})"
    else:
        cmf_desc = f"中性 (CMF {cmf:.2f})"

    price_trend = df["close"].iloc[-1] - df["close"].iloc[-10]

    if (
        (price_trend > 0 and obv_trend > 0)
        or
        (price_trend < 0 and obv_trend < 0)
    ):
        obv_desc = "量价同步"
    else:
        obv_desc = "量价背离"

    if vol < 0.3:
        vol_desc = f"低 ({vol:.2f}%)"
    elif vol < 0.8:
        vol_desc = f"中等 ({vol:.2f}%)"
    else:
        vol_desc = f"高 ({vol:.2f}%)"

    msg = (
        f"📊 BTC市场状态 ({pd.Timestamp.now().strftime('%H:%M')})\n"
        f"价格: {price:,.1f}\n"
        f"趋势: {macd_desc}\n"
        f"资金流向: {cmf_desc}\n"
        f"量价关系: {obv_desc}\n"
        f"波动率: {vol_desc}"
    )

    return msg


def main_loop():
    print("BOT_TOKEN =", BOT_TOKEN is not None)
    print("CHAT_ID =", CHAT_ID)

    send_telegram("🚀 市场状态播报启动（每小时更新）")

    while True:
        msg = describe_market()
        send_telegram(msg)

        time.sleep(60 * 60)


if __name__ == "__main__":
    while True:
        try:
            main_loop()

        except Exception:
            err = traceback.format_exc()

            print(err)

            send_telegram(
                "⚠️ 程序异常\n\n"
                + err[:3000]
            )

            time.sleep(30)
