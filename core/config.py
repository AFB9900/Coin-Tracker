import os
from dotenv import load_dotenv

# .env dosyasını tek bir merkezden yüklüyoruz
load_dotenv()

DB_FILE = "crypto_tracker.db"

# Güvenlik Ayarları
# Canlıya çıkarken .env içinde güçlü bir SECRET_KEY tanımlayabilirsin
SECRET_KEY = os.getenv("SECRET_KEY", "KGM_Yilgar_Gokboru_Secret_Key_2026")
SESSION_SECRET = SECRET_KEY
SESSION_COOKIE_NAME = "session_user"

# Genel popüler coin listesi
POPULAR_COINS = ["SOL", "AVAX", "DOGE", "XRP", "LINK", "BEAT"]