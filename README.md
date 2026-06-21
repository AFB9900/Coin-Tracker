# Coin-Tracker / Quant Terminal Pro — Bitcoin Tracker

Minimal, async odaklı kripto takip uygulaması.

Özellikler
- FastAPI + Jinja2 tabanlı arayüz
- Asenkron fiyat takip döngüsü (httpx)
- Kullanıcıya özel takip listesi (SQLite)
- TradingView widget ile profesyonel grafik gösterimi
- Llama/ollama tabanlı yerel AI analiz (opsiyonel)

Hızlı başlangıç

1. Ortamı hazırla

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2. Çalıştır

```bash
python -m uvicorn main:app --reload
```

3. Tarayıcıda aç

http://127.0.0.1:8000

Ortam değişkenleri
- `SECRET_KEY` — opsiyonel, oturum güvenliği için.
- `.env` dosyasına ekleyebilirsiniz.

Notlar
- TradingView widget internet bağlantısı gerektirir.
- Veritabanı dosyası `crypto_tracker.db` proje kökünde oluşturulur; prod için harici bir veritabanı tercih edin.

Katkıda bulunma
- Küçük değişiklikler için PR açın veya issue bildirin.

License
- MIT (varsayılan)
