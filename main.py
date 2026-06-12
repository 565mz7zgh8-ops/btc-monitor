import requests, time, os
import pandas as pd
import numpy as np

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"
BINANCE_TRADES = "https://api.binance.com/api/v3/aggTrades"

def send_telegram(msg):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": msg})

def get_klines(symbol="BTCUSDT", interval="15m", limit=100):
    r = requests.get(BINANCE_KLINES, params={
        "symbol": symbol, "interval": interval, "limit": limit
    })
    data = r.json()
    df = pd.DataFrame(data, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","qav","trades","taker_base","taker_quote","ignore"
    ])
    for col in ["open","high","low","close","volume","taker_base"]:
        df[col] = df[col].astype(float)
    return df

# ---------- 指标计算 ----------

def calc_macd(df, fast=12, slow=26, signal=9):
    ema_fast = df["close"].ewm(span=fast).mean()
    ema_slow = df["close"].ewm(span=slow).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal).mean()
    hist = macd - signal_line
    return macd, signal_line, hist

def calc_cmf(df, period=20):
    mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / (df["high"] - df["low"])
    mfm = mfm.replace([np.inf, -np.inf], 0).fillna(0)
    mfv = mfm * df["volume"]
    cmf = mfv.rolling(period).sum() / df["volume"].rolling(period).sum()
    return cmf

def calc_obv(df):
    direction = np.sign(df["close"].diff()).fillna(0)
    obv = (direction * df["volume"]).cumsum()
    return obv

def calc_cvd(df):
    # taker_base = 主动买入量；总量 - 主动买入 = 主动卖出量
    delta = df["taker_base"] - (df["volume"] - df["taker_base"])
    cvd = delta.cumsum()
    return cvd

# ---------- 信号检测 ----------

def check_signals(df):
    signals = []
    
    macd, sig, hist = calc_macd(df)
    cmf = calc_cmf(df)
    obv = calc_obv(df)
    cvd = calc_cvd(df)
    
    price = df["close"].iloc[-1]
    
    # MACD 金叉/死叉
    if hist.iloc[-2] < 0 and hist.iloc[-1] > 0:
        signals.append(f"📊 MACD 金叉 (柱状由负转正)")
    elif hist.iloc[-2] > 0 and hist.iloc[-1] < 0:
        signals.append(f"📊 MACD 死叉 (柱状由正转负)")
    
    # CMF 资金流向极值
    cmf_now = cmf.iloc[-1]
    if cmf_now > 0.2:
        signals.append(f"💰 CMF 资金流入强劲 ({cmf_now:.2f})")
    elif cmf_now < -0.2:
        signals.append(f"💸 CMF 资金流出强劲 ({cmf_now:.2f})")
    
    # OBV 与价格背离（简单判断：最近10根，价格新高但OBV未新高）
    recent_price = df["close"].iloc[-10:]
    recent_obv = obv.iloc[-10:]
    if recent_price.iloc[-1] == recent_price.max() and recent_obv.iloc[-1] < recent_obv.max():
        signals.append(f"⚠️ OBV 顶背离 (价格新高但量能未跟上)")
    if recent_price.iloc[-1] == recent_price.min() and recent_obv.iloc[-1] > recent_obv.min():
        signals.append(f"⚠️ OBV 底背离 (价格新低但量能未跟上)")
    
    # CVD 趋势 vs 价格趋势 背离
    recent_cvd = cvd.iloc[-10:]
    if recent_price.iloc[-1] > recent_price.iloc[0] and recent_cvd.iloc[-1] < recent_cvd.iloc[0]:
        signals.append(f"🔍 CVD 背离: 价格涌升但主动卖盘占优")
    if recent_price.iloc[-1] < recent_price.iloc[0] and recent_cvd.iloc[-1] > recent_cvd.iloc[0]:
        signals.append(f"🔍 CVD 背离: 价格下跌但主动买盘占优")
    
    return signals, price, macd.iloc[-1], cmf_now, obv.iloc[-1], cvd.iloc[-1]

# ---------- 主循环 ----------

def main_loop():
    send_telegram("🚀 BTC 多指标监控启动 (15m K线: MACD/CMF/OBV/CVD)")
    last_price = None
    
    while True:
        df = get_klines(interval="15m", limit=100)
        signals, price, macd_val, cmf_val, obv_val, cvd_val = check_signals(df)
        
        # 价格波动提醒
        if last_price is not None:
            change_pct = (price - last_price) / last_price * 100
            if abs(change_pct) >= 1:
                signals.append(f"💹 价格变动 {change_pct:+.2f}%")
        last_price = price
        
        if signals:
            msg = f"BTC: {price}\n" + "\n".join(signals)
            send_telegram(msg)
        
        time.sleep(60 * 15)  # 每15分钟检查一次（匹配K线周期）

if __name__ == "__main__":
    while True:
        try:
            main_loop()
        except Exception as e:
            import traceback
            send_telegram(f"⚠️ 异常:\n{traceback.format_exc()}")
            time.sleep(30)
