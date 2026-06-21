import httpx
import pandas as pd
import ta


def normalize_symbol(symbol: str):
    if not symbol:
        return None
    cleaned = symbol.upper().strip().replace(" ", "").replace("-", "").replace("/", "")
    if cleaned.endswith("USDT"):
        cleaned = cleaned[:-4]
    if not cleaned.isalnum():
        return None
    return f"{cleaned}USDT"


def analyze_technical_indicators(klines_data):
    """Mum verilerini DataFrame'e çevirip gelişmiş momentum ve hacim analizleri yapar."""
    df = pd.DataFrame(klines_data, columns=['time', 'open', 'high', 'low', 'close', 'volume'])
    
    # 1. Momentum ve Trend Göstergeleri
    df['rsi'] = ta.momentum.rsi(close=df['close'], window=14)
    macd_object = ta.trend.MACD(close=df['close'], window_fast=12, window_slow=26, window_sign=9)
    df['macd'] = macd_object.macd()
    df['macd_signal'] = macd_object.macd_signal()
    df['macd_diff'] = macd_object.macd_diff()
    
    bollinger = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
    df['bb_high'] = bollinger.bollinger_hband()
    df['bb_low'] = bollinger.bollinger_lband()
    df['bb_mid'] = bollinger.bollinger_mavg()
    
    df['ema20'] = ta.trend.ema_indicator(close=df['close'], window=20)
    df['ema50'] = ta.trend.ema_indicator(close=df['close'], window=50)
    
    # 2. Kurumsal Hacim ve Para Akışı Göstergeleri (Volume Flow)
    df['obv'] = ta.volume.on_balance_volume(close=df['close'], volume=df['volume'])
    df['cmf'] = ta.volume.chaikin_money_flow(high=df['high'], low=df['low'], close=df['close'], volume=df['volume'], window=20)
    df['vpt'] = ta.volume.volume_price_trend(close=df['close'], volume=df['volume'])
    
    latest = df.iloc[-1]
    previous = df.iloc[-2]
    
    # Algoritmik Sinyal Üretim İstasyonu
    signals = []
    if latest['rsi'] < 30: signals.append("RSI Aşırı Satım (Dip)")
    elif latest['rsi'] > 70: signals.append("RSI Aşırı Alım (Tepe)")
    
    if latest['macd'] > latest['macd_signal']: signals.append("MACD Boğa Kesişimi (Al)")
    else: signals.append("MACD Ayı Kesişimi (Sat)")
    
    if latest['cmf'] > 0.05: signals.append("CMF Pozitif (Kurumsal Para Girişi)")
    elif latest['cmf'] < -0.05: signals.append("CMF Negatif (Kurumsal Para Çıkışı)")
        
    obv_trend = "Yükseliyor (Hacim Akışı Pozitif)" if latest['obv'] > previous['obv'] else "Düşüyor (Hacim Akışı Zayıf)"
        
    return {
        "rsi": float(latest['rsi']),
        "macd": float(latest['macd']),
        "macd_signal": float(latest['macd_signal']),
        "macd_diff": float(latest['macd_diff']),
        "bb_high": float(latest['bb_high']),
        "bb_low": float(latest['bb_low']),
        "bb_mid": float(latest['bb_mid']),
        "ema20": float(latest['ema20']),
        "ema50": float(latest['ema50']),
        "obv": float(latest['obv']),
        "cmf": float(latest['cmf']),
        "vpt": float(latest['vpt']),
        "obv_trend": obv_trend,
        "signals": ", ".join(signals)
    }

async def fetch_comprehensive_ticker_async(symbol: str):
    """Sertifika doğrulaması aktif, httpx tabanlı tamamen asenkron borsa fiyat çekicisi."""
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}", timeout=3.0)
            if res.status_code == 200:
                data = res.json()
                data["market_type"] = "spot"
                return data
        except Exception: pass
        
        try:
            res = await client.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol}", timeout=3.0)
            if res.status_code == 200:
                data = res.json()
                data["market_type"] = "futures"
                return data
        except Exception: pass
    return None