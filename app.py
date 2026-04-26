import os
import sqlite3
import requests
import random
from flask import Flask, render_template, abort
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from googletrans import Translator
from newspaper import Article
from concurrent.futures import ThreadPoolExecutor
# اضافه کردن کتابخانه زمان‌بندی حرفه‌ای
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
translator = Translator()

TOKEN = os.environ.get("TOKEN")
CHAT_ID = "@XNewNewsMavara"
MY_SITE_URL = "https://voluntary-linn-shapyaar-22266960.koyeb.app"
DB_PATH = "news.db"

# --- لیست منابع ---
SOURCES = [
    {"name": "ایران اینترنشنال", "url": "https://www.iranintl.com/rss/all"},
    {"name": "بی بی سی فارسی", "url": "https://www.bbc.com/persian/index.xml"},
    {"name": "رادیو فردا", "url": "https://www.radiofarda.com/api/z$qppe_kq_"},
    {"name": "دویچه وله", "url": "https://www.dw.com/fa/persian/s-3277"},
    {"name": "تایمز اسرائیل", "url": "https://www.timesofisrael.com/feed/"},
    {"name": "جروزالم پست", "url": "https://www.jpost.com/rss/rssfeeds.aspx?catid=1"},
    {"name": "رویترز", "url": "https://www.reutersagency.com/feed/"},
    {"name": "توییتر ترامپ", "url": "https://nitter.cz/realDonaldTrump/rss"},
    {"name": "توییتر نتانیاهو", "url": "https://nitter.cz/netanyahu/rss"},
    {"name": "توییتر رضا پهلوی", "url": "https://nitter.cz/PahlaviReza/rss"}
]

# --- توابع اصلی (بدون تغییر نسبت به قبل) ---
def ai_translate(text):
    try:
        if not text: return ""
        clean_text = BeautifulSoup(text, "html.parser").get_text().strip()
        if any('\u0600' <= char <= '\u06FF' for char in clean_text[:30]):
            return f"\u200f{clean_text}\u200f"
        return f"\u200f{translator.translate(clean_text, dest='fa').text}\u200f"
    except: return text

def process_source(src):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS news (id INTEGER PRIMARY KEY AUTOINCREMENT, title_fa TEXT, desc_fa TEXT, source TEXT, link TEXT UNIQUE, pub_date DATETIME)''')
        
        res = requests.get(src['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
        soup = BeautifulSoup(res.content, "xml")
        limit_time = datetime.now(timezone.utc) - timedelta(hours=12)

        for item in soup.find_all('item')[:10]:
            link = item.link.text
            c.execute("SELECT id FROM news WHERE link=?", (link,))
            if c.fetchone(): continue

            try:
                p_date = parsedate_to_datetime(item.pubDate.text)
                if p_date.tzinfo is None: p_date = p_date.replace(tzinfo=timezone.utc)
                if p_date < limit_time: continue
                pub_date_iso = p_date.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pub_date_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # --- بخش اصلاح شده برای ترجمه متن خبر ---
            # ابتدا سعی می‌کند متن کامل را از لینک اصلی استخراج کند
            full_txt = get_full_content(link)
            # اگر نشد، از همان توضیحات کوتاه RSS استفاده می‌کند
            if not full_txt: 
                full_txt = item.description.text if item.description else "متنی یافت نشد"

            title_fa = ai_translate(item.title.text)
            desc_fa = ai_translate(full_txt) # حالا متن خبر هم ترجمه می‌شود

            c.execute("INSERT INTO news (title_fa, desc_fa, source, link, pub_date) VALUES (?, ?, ?, ?, ?)",
                      (title_fa, desc_fa, src['name'], link, pub_date_iso))
            news_id = c.lastrowid
            conn.commit()
            
            # حالا اطلاعات کامل (تیتر + متن ترجمه شده) به تلگرام فرستاده می‌شود
            send_to_telegram(title_fa, desc_fa, news_id, src['name'], pub_date_iso)
            
        conn.close()
    except Exception as e: 
        print(f"خطا در پردازش {src['name']}: {e}")
def scheduled_update():
    print(f"شروع آپدیت خودکار: {datetime.now()}")
    shuffled = SOURCES.copy()
    random.shuffle(shuffled)
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(process_source, shuffled)
    print("آپدیت خودکار با موفقیت انجام شد.")

# --- راه‌اندازی زمان‌بند (Scheduler) ---
scheduler = BackgroundScheduler(daemon=True)
# تنظیم اجرای آپدیت هر ۱۰ دقیقه یک‌بار
scheduler.add_job(func=scheduled_update, trigger="interval", minutes=10)
scheduler.start()

@app.route('/')
def home():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title_fa, source, pub_date FROM news WHERE pub_date >= datetime('now', '-12 hours') ORDER BY pub_date DESC LIMIT 60")
    news_list = c.fetchall()
    conn.close()
    return render_template('index.html', news=news_list)

if __name__ == "__main__":
    # اجرای یک آپدیت اولیه بلافاصله بعد از بالا آمدن سرور
    scheduled_update()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))
