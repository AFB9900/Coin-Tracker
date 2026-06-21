import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import httpx
import uvicorn
import time
import sqlite3

# 📂 Kendi yazdığımız yeni modülleri içeri alıyoruz
from core.config import DB_FILE, POPULAR_COINS
from services.auth import get_user_by_username, get_current_user, hash_password, verify_password, make_session_cookie
from services.crypto import analyze_technical_indicators, normalize_symbol
from services.ai import build_quant_prompt, generate_ai_report

# Global bellek alanları (Hafif ve hızlı önbellekleme için)
popular_coins_prices = {}
usdt_try_rate = 34.50

# =====================================================================
# 🗄️ SQLITE VERİTABANI İLKLENDİRME
# =====================================================================
def init_db():
    """Çok kullanıcılı SQLite tablolarını thread-safe modda tetikler."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    
    # Kullanıcılar Tablosu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            telegram_token TEXT,
            telegram_chat_id TEXT
        )
    """)
    
    # Kullanıcıya Bağımlı İzleme Listesi
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            upper_limit REAL,
            lower_limit REAL,
            market_type TEXT,
            UNIQUE(user_id, symbol),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

# =====================================================================
# 📡 ASYNC TELEGRAM BİLDİRİM MOTORU (HTTPX)
# =====================================================================
async def send_telegram_message_async(token: str, chat_id: str, message: str):
    """Bloklama yapmayan tamamen asenkron Telegram fırlatıcısı."""
    if token and chat_id:
        async with httpx.AsyncClient() as client:
            try:
                url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
                await client.post(url, json=payload, timeout=3.0)
            except Exception as e:
                print(f"Telegram async bildirim hatası: {e}")

# =====================================================================
# ⏱️ HTTPX TABANLI ASYNC ARKA PLAN ALARM MOTORU
# =====================================================================
async def fetch_ticker_internal_async(client: httpx.AsyncClient, symbol: str):
    """Arka plan motoru için optimize edilmiş hızlı async fiyat çekici."""
    try:
        res = await client.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}", timeout=2.0)
        if res.status_code == 200:
            data = res.json()
            data["market_type"] = "spot"
            return data
    except Exception: pass
    try:
        res = await client.get(f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={symbol}", timeout=2.0)
        if res.status_code == 200:
            data = res.json()
            data["market_type"] = "futures"
            return data
    except Exception: pass
    return None

async def track_crypto_prices_async():
    """Requests bloklamalarından arındırılmış %100 Async 7/24 döngü."""
    global usdt_try_rate
    print("🛰️ Async HTTPX Altyapılı Alarm Döngüsü 7/24 Aktif Edildi.")

    async with httpx.AsyncClient() as client:
        while True:
            # 1. Dolar Kurunu Güncelle
            try:
                usdt_res = await client.get("https://api.binance.com/api/v3/ticker/price?symbol=USDTTRY", timeout=2.0)
                if usdt_res.status_code == 200:
                    usdt_try_rate = float(usdt_res.json()["price"])
            except Exception: pass

            # 2. Popüler Coin Panelini Güncelle
            for coin in POPULAR_COINS:
                sym = f"{coin}USDT"
                ticker = await fetch_ticker_internal_async(client, sym)
                if ticker:
                    popular_coins_prices[coin] = {
                        "price": float(ticker["lastPrice"]),
                        "change": float(ticker["priceChangePercent"])
                    }

            # 3. Kullanıcı Alarmlarını Güvenli Sorgula
            try:
                conn = sqlite3.connect(DB_FILE, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT w.symbol, w.upper_limit, w.lower_limit, u.telegram_token, u.telegram_chat_id, w.id
                    FROM watchlist w
                    JOIN users u ON w.user_id = u.id
                """)
                all_alarms = [dict(row) for row in cursor.fetchall()]
                conn.close()

                for alarm in all_alarms:
                    sym = alarm["symbol"]
                    ticker = await fetch_ticker_internal_async(client, sym)
                    if ticker:
                        curr_price = float(ticker["lastPrice"])
                        
                        if curr_price >= alarm["upper_limit"] and alarm["upper_limit"] != 999999.0:
                            await send_telegram_message_async(alarm["telegram_token"], alarm["telegram_chat_id"], f"⚠️ *LİMİT ALARMI (ÜST)*\n🔴 `{sym}` üst limiti aştı!\nFiyat: `${curr_price:,.2f}`")
                        elif curr_price <= alarm["lower_limit"] and alarm["lower_limit"] != 0.0:
                            await send_telegram_message_async(alarm["telegram_token"], alarm["telegram_chat_id"], f"⚠️ *LİMİT ALARMI (ALT)*\n🟢 `{sym}` alt limitin altına düştü!\nFiyat: `${curr_price:,.2f}`")
            except Exception as e:
                print(f"Async alarm tarayıcı hatası: {e}")

            await asyncio.sleep(4)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(track_crypto_prices_async())
    yield
    task.cancel()

app = FastAPI(title="Quant Terminal Pro", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")

# =====================================================================
# 🔐 AUTH ROUTER KATMANI
# =====================================================================
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login")
async def handle_login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Hatalı kullanıcı adı veya şifre!"})
    
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="session_user", value=make_session_cookie(username.strip()), max_age=86400, httponly=True, samesite="lax")
    return response

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "error": None})

@app.post("/register")
async def handle_register(request: Request, username: str = Form(...), password: str = Form(...), telegram_token: str = Form(None), telegram_chat_id: str = Form(None)):
    if get_user_by_username(username):
        return templates.TemplateResponse("register.html", {"request": request, "error": "Bu kullanıcı adı veritabanında mevcut!"})
    
    h_pass = hash_password(password)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (username, password_hash, telegram_token, telegram_chat_id)
        VALUES (?, ?, ?, ?)
    """, (username.strip(), h_pass, telegram_token.strip() if telegram_token else None, telegram_chat_id.strip() if telegram_chat_id else None))
    conn.commit()
    conn.close()
    return templates.TemplateResponse("login.html", {"request": request, "success": "Hesabınız başarıyla oluşturuldu. Giriş yapabilirsiniz."})

@app.get("/logout")
async def handle_logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_user")
    return response

# =====================================================================
# 🌐 KULLANICIYA ÖZEL ASYNC API VE INTERFACE ENDPOINTS
# =====================================================================
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        get_current_user(request)
        return templates.TemplateResponse("index.html", {"request": request})
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

@app.get("/api/status")
async def get_status(request: Request):
    try:
        user = get_current_user(request)
    except HTTPException:
        return {"error": "Unauthorized"}

    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT symbol, upper_limit, lower_limit, market_type FROM watchlist WHERE user_id = ?", (user["id"],))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    user_watchlist = {}
    async with httpx.AsyncClient() as client:
        for row in rows:
            sym = row["symbol"]
            ticker = await fetch_ticker_internal_async(client, sym)
            user_watchlist[sym] = {
                "current_price": float(ticker["lastPrice"]) if ticker else 0.0,
                "price_change_24h": float(ticker["priceChangePercent"]) if ticker else 0.0,
                "upper_limit": row["upper_limit"], "lower_limit": row["lower_limit"], "market_type": row["market_type"]
            }

    return {"status": "Aktif", "usdt_try": usdt_try_rate, "watchlist": user_watchlist, "discovery_prices": popular_coins_prices}

@app.post("/api/add-coin")
async def add_coin(request: Request, symbol: str = Form(...), upper_limit: float = Form(...), lower_limit: float = Form(...)):
    user = get_current_user(request)
    formatted = symbol.upper().strip()
    if not formatted.endswith("USDT"): formatted += "USDT"
    
    async with httpx.AsyncClient() as client:
        ticker = await fetch_ticker_internal_async(client, formatted)
    m_type = ticker["market_type"] if ticker else "spot"

    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO watchlist (user_id, symbol, upper_limit, lower_limit, market_type)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, symbol) DO UPDATE SET upper_limit=excluded.upper_limit, lower_limit=excluded.lower_limit, market_type=excluded.market_type
    """, (user["id"], formatted, upper_limit, lower_limit, m_type))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/api/quick-add")
async def quick_add(request: Request, symbol: str = Form(...)):
    user = get_current_user(request)
    formatted = symbol.upper().strip()
    if not formatted.endswith("USDT"): formatted += "USDT"
    
    async with httpx.AsyncClient() as client:
        ticker = await fetch_ticker_internal_async(client, formatted)
    m_type = ticker["market_type"] if ticker else "spot"

    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO watchlist (user_id, symbol, upper_limit, lower_limit, market_type)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, symbol) DO NOTHING
    """, (user["id"], formatted, 999999.0, 0.0, m_type))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

@app.post("/api/delete-coin")
async def delete_coin(request: Request, symbol: str = Form(...)):
    user = get_current_user(request)
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watchlist WHERE user_id = ? AND symbol = ?", (user["id"], symbol))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

# =====================================================================
# 🤖 ASYNC QUANT AJAN OPERASYONU (ORDER BOOK VE ÇOKLU ZAMAN DİLİMİ)
# =====================================================================
@app.get("/api/ai-analyze/{symbol}")
async def analyze_with_ai(request: Request, symbol: str):
    try:
        get_current_user(request)
    except HTTPException:
        return {"analysis": "Yetkisiz oturum."}

    async with httpx.AsyncClient() as client:
        ticker = await fetch_ticker_internal_async(client, symbol)
        if not ticker:
            return {"analysis": "Borsa bağlantı hatası."}

        price = float(ticker.get("lastPrice", 0))
        m_type = ticker["market_type"]
        base_url = "https://api.binance.com/api/v3" if m_type == "spot" else "https://fapi.binance.com/fapi/v1"

        # 📊 Çoklu Zaman Dilimi Verilerini Paralel Çekme
        tech_1h, tech_4h = {"rsi": 50.0, "signals": "", "ema20": price, "bb_mid": price}, {"rsi": 50.0, "signals": "", "ema50": price}
        try:
            res_1h = await client.get(f"{base_url}/klines?symbol={symbol}&interval=1h&limit=100", timeout=3.0)
            if res_1h.status_code == 200:
                candles_1h = [[int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])] for c in res_1h.json()]
                tech_1h = analyze_technical_indicators(candles_1h)
                
            res_4h = await client.get(f"{base_url}/klines?symbol={symbol}&interval=4h&limit=100", timeout=3.0)
            if res_4h.status_code == 200:
                candles_4h = [[int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])] for c in res_4h.json()]
                tech_4h = analyze_technical_indicators(candles_4h)
        except Exception: pass

        # 🐋 Canlı Sipariş Defteri Balina Duvarları
        buy_walls, sell_walls = [], []
        try:
            depth_res = await client.get(f"{base_url}/depth?symbol={symbol}&limit=50", timeout=2.0)
            if depth_res.status_code == 200:
                depth = depth_res.json()
                bids = sorted(depth.get("bids", []), key=lambda x: float(x[1]), reverse=True)[:3]
                asks = sorted(depth.get("asks", []), key=lambda x: float(x[1]), reverse=True)[:3]
                buy_walls = [f"Fiyat: ${float(b[0]):,.2f} (Miktar: {float(b[1]):,.1f})" for b in bids]
                sell_walls = [f"Fiyat: ${float(a[0]):,.2f} (Miktar: {float(a[1]):,.1f})" for a in asks]
        except Exception: pass

        # 🌍 Makro Haber ve Korku Endeksi Çekimi
        news_summary = "Genel makro borsa haber akışına şu an ulaşılamadı."
        try:
            news_res = await client.get("https://cryptopanic.com/api/v1/posts/?posts=true&public=true", timeout=3.0)
            if news_res.status_code == 200:
                news_data = news_res.json().get("results", [])[:3]
                news_summary = "\n".join([f"- {n.get('title')}" for n in news_data])
        except Exception: pass

        fear_greed_status = "Bilinmiyor"
        try:
            f_g_res = await client.get("https://api.alternative.me/fng/", timeout=2.0)
            if f_g_res.status_code == 200:
                f_data = f_g_res.json().get("data", [{}])[0]
                fear_greed_status = f"{f_data.get('value')}/100 ({f_data.get('value_classification')})"
        except Exception: pass

    # Modüler Prompt Oluşturucu ve Yerel AI Tetikleyicisi
    prompt = build_quant_prompt(symbol, price, ticker, tech_1h, tech_4h, buy_walls, sell_walls, news_summary, fear_greed_status)
    analysis_result = generate_ai_report(prompt)
    
    return {"analysis": analysis_result}

# =====================================================================
# 📊 YARDIMCI API UÇ NOKTALARI (TRADES & KLINES)
# =====================================================================
@app.get("/api/trades/{symbol}")
async def get_recent_trades(symbol: str):
    async with httpx.AsyncClient() as client:
        ticker = await fetch_ticker_internal_async(client, symbol)
        if not ticker: return []
        base_url = "https://api.binance.com/api/v3" if ticker["market_type"] == "spot" else "https://fapi.binance.com/fapi/v1"
        try:
            res = await client.get(f"{base_url}/trades?symbol={symbol}&limit=12", timeout=3.0)
            if res.status_code == 200:
                trades = []
                for t in res.json():
                    trades.append({
                        "time": time.strftime('%H:%M:%S', time.localtime(t['time']/1000)),
                        "price": float(t['price']), "qty": float(t['qty']), "is_buyer_maker": t.get('isBuyerMaker', t.get('buyer', False))
                    })
                return trades[::-1]
        except Exception: pass
    return []

@app.get("/api/klines/{symbol}")
async def get_klines(symbol: str, interval: str = "1h"):
    async with httpx.AsyncClient() as client:
        ticker = await fetch_ticker_internal_async(client, symbol)
        if not ticker: raise HTTPException(status_code=404, detail="Parite bulunamadı")
        base_url = "https://api.binance.com/api/v3" if ticker["market_type"] == "spot" else "https://fapi.binance.com/fapi/v1"
        try:
            res = await client.get(f"{base_url}/klines?symbol={symbol}&interval={interval}&limit=150", timeout=4.0)
            if res.status_code == 200:
                return [{"time": int(item[0] / 1000), "open": float(item[1]), "high": float(item[2]), "low": float(item[3]), "close": float(item[4])} for item in res.json()]
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/coin/{symbol}", response_class=HTMLResponse)
async def coin_detail(request: Request, symbol: str):
    try:
        get_current_user(request)
        async with httpx.AsyncClient() as client:
            ticker = await fetch_ticker_internal_async(client, symbol)
        m_type = ticker["market_type"] if ticker else "spot"
        return templates.TemplateResponse("detail.html", {"request": request, "symbol": symbol, "market_type": m_type})
    except HTTPException:
        return RedirectResponse(url="/login", status_code=303)

if __name__ == "__main__": 
    # Canlı sunucu (Production) modunda host "0.0.0.0" olarak tüm ağlara açıldı.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)