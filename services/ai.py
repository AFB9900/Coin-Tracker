import ollama

def build_quant_prompt(symbol: str, price: float, ticker_data: dict, tech_1h: dict, tech_4h: dict, buy_walls: list, sell_walls: list, news_summary: str, fear_greed_status: str) -> str:
    """Yapay zekanın kuralları dışarı sızdırmadan kurumsal analiz yapmasını sağlayan İngilizce prompt şablonu."""
    return (
        f"System Role: You are a Senior Quantitative (Quant) Trader and Technical Analyst at a top-tier hedge fund.\n"
        f"Task: Generate a highly professional, contradiction-free trading report for institutional clients using the provided terminal data.\n\n"
        f"DATA INPUTS:\n"
        f"- Target Asset: {symbol}\n"
        f"- Spot Price: ${price:,.2f} | 24h Range: ${float(ticker_data.get('lowPrice', 0)):,.2f} - ${float(ticker_data.get('highPrice', 0)):,.2f} | Change: %{ticker_data.get('priceChangePercent', '0.0')}\n"
        f"- 24h Cash Volume: ${float(ticker_data.get('quoteVolume', 0)):,.2f} USDT\n\n"
        f"⏳ Timeframe Confluence:\n"
        f"  [1-Hour Micro]: RSI: {tech_1h['rsi']:.2f} | Signals: {tech_1h['signals']} | EMA20: ${tech_1h['ema20']:,.2f} | Bollinger Mid: ${tech_1h['bb_mid']:,.2f}\n"
        f"  [4-Hour Macro]: RSI: {tech_4h['rsi']:.2f} | Signals: {tech_4h['signals']} | EMA50: ${tech_4h['ema50']:,.2f}\n\n"
        f"🐋 Live Order Book Order Walls (Massive Liquidity Clusters):\n"
        f"  - Major Pending Buy Orders (Support Blocks):\n  " + "\n  ".join(buy_walls) + "\n"
        f"  - Major Pending Sell Orders (Resistance Blocks):\n  " + "\n  ".join(sell_walls) + "\n\n"
        f"🌍 Global News Sentiment:\n{news_summary}\n"
        f"- Market Emotion Index: {fear_greed_status}\n\n"
        f"❌ FORBIDDEN IN OUTPUT:\n"
        f"- DO NOT print any instruction text, code variables, or rules like 'MATHEMATICAL CONSISTENCY' or 'GUARDRAILS'.\n"
        f"- DO NOT output any English text. The final response must be pure Turkish.\n\n"
        f"⭕ CRITICAL ANALYSIS LOGIC:\n"
        f"- Evaluate whether the 4-Hour macro trend confirms or denies the 1-Hour micro movement.\n"
        f"- Use the Live Order Book walls to pin-point the exact absolute Support and Resistance targets instead of guessing.\n\n"
        f"Structure your final report in TURKISH with these exact markdown headers:\n"
        f"**Kurumsal Analiz Raporu**\n"
        f"**1. Teknik Göstergeler ve Çoklu Zaman Dilimi Momentum Değerlendirmesi**\n"
        f"**2. Kurumsal Hacim Flow ve Canlı Balina Emir Defteri (Order Book) Analizi**\n"
        f"**3. Makro Gündem ve Yatırımcı Psikolojisi**\n"
        f"**4. Al/Sat/Bekle Stratejisi (Aksiyon Planı)**\n\n"
        f"Conclude with a clean professional disclaimer (Yatırım tavsiyesi değildir)."
    )

def generate_ai_report(prompt: str) -> str:
    """Yerelde çalışan Llama 3 modeline bağlanarak analiz raporunu üretir."""
    try:
        response = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': prompt}])
        return response['message']['content']
    except Exception as e:
        return f"Yerel yapay zeka ajanına bağlanırken hata oluştu: {str(e)}"