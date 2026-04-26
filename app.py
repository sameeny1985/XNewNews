import os
import sqlite3
import requests
import random
import threading
import time
import subprocess
import sys
from flask import Flask, render_template, abort
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from newspaper import Article
from concurrent.futures import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
import translators as ts

app = Flask(__name__)

# --- تنظیمات اصلی ---
TOKEN = os.environ.get("TOKEN")
CHAT_ID = "@XNewNewsMavara"
MY_SITE_URL = "https://voluntary-linn-shapyaar-22266960.koyeb.app/"
DB_PATH = "news.db"

# --- لیست منابع (RSS و Nitter) ---
SOURCES = [
    {"name": "ایران اینترنشنال", "url": "https://news.google.com/rss/search?q=Iran+International&hl=fa&gl=IR&ceid=IR:fa"},
    {"name": "صدای آمریکا (VOA)", "url": "https://ir.voanews.com/api/z$p_eyuvt_"},
    {"name": "رادیو فردا", "url": "https://www.radiofarda.com/api/zsqym_egiv"},
    {"name": "بی‌بی‌سی فارسی", "url": "https://www.bbc.com/persian/index.xml"},
    {"name": "دویچه وله (DW)", "url": "https://rss.dw.com/rdf/rss-fa-all"},
    {"name": "خبرگزاری فارس", "url": "https://www.farsnews.ir/rss"},
    {"name": "رویترز (Reuters)", "url": "https://www.reutersagency.com/feed/"},
    {"name": "CNN (Iran Focus)", "url": "https://news.google.com/rss/search?q=CNN+Iran&hl=en&gl=US&ceid=US:en"},
    {"name": "Fox News (Iran Focus)", "url": "https://news.google.com/rss/search?q=Fox+News+Iran&hl=en&gl=US&ceid=US:en"},
    {"name": "رادیو پیام اسرائیل", "url": "https://radisrael.com/feed/"},
    {"name": "تایمز اسرائیل (فارسی)", "url": "https://fa.timesofisrael.com/feed/"},
    {"name": "توییتر ترامپ", "url": "https://nitter.net/realDonaldTrump/rss"},
    {"name": "توییتر نتانیاهو", "url": "https://nitter.net/netanyahu/rss"},
    {"name": "Jerusalem Post", "url": "https://nitter.net/Jerusalem_Post/rss"},
    {"name": "Times of Israel", "url": "https://nitter.net/TimesofIsrael/rss"}
]

# --- تابع هوشمند ترجمه ---
def ai_translate(text):
    if not text or len(text.strip()) < 5: 
        return text
    try:
        # پاکسازی HTML
        clean_text = BeautifulSoup(text, "html.parser").get_text().strip()
        
        # تشخیص زبان: اگر فارسی بود ترجمه نکن
        sample = clean_text[:50]
        farsi_chars = sum(1 for char in sample if '\u0600' <= char <= '\u06FF')
        if farsi_chars > (len(sample) / 2):
            return f"\u200f{clean_text}\u200f"

        time.sleep(1.2) # وقفه برای جلوگیری از بلاک شدن
        
        # ترجمه با موتور گوگل (پایدارترین حالت)
        translated = ts.translate_text(clean_text, from_language='auto', to_language='fa', engine='google')
        return f"\u200f{translated}\u200f"
    except Exception as e:
        print(f"Translation Error: {e}")
        return text

# --- تابع ارسال به تلگرام ---
def send_to_telegram(title_fa, desc_fa, news_id, source_name, pub_date):
    if not TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        message_text = (
            f"🔴 <b>{title_fa}</b>\n\n"
            f"🔹 منبع: {source_name}\n"
            f"⏰ زمان: {pub_date}\n"
            f"📝 {desc_fa[:450]}...\n\n"
            f"🆔 @XNewNewsMavara"
        )
        payload = {
            "chat_id": CHAT_ID,
            "text": message_text,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [[
                    {"text": "📖 مشاهده کامل خبر", "url": f"{MY_SITE_URL}/news/{news_id}"}
                ]]
            }
        }
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"Telegram Error: {e}")

# --- استخراج متن اصلی مقاله ---
def get_full_content(url):
    try:
        article = Article(url)
        article.config.browser_user_agent = 'Mozilla/5.0'
        article.config.request_timeout = 15
        article.download()
        article.parse()
        return article.text if len(article.text) > 100 else ""
    except: return ""

# --- پردازش هر منبع خبری ---
def process_source(src):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS news (id INTEGER PRIMARY KEY AUTOINCREMENT, title_fa TEXT, desc_fa TEXT, source TEXT, link TEXT UNIQUE, pub_date DATETIME)''')
        
        res = requests.get(src['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
        soup = BeautifulSoup(res.content, "xml")
        limit_time = datetime.now(timezone.utc) - timedelta(hours=24)

        for item in soup.find_all('item')[:8]:
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

            # دریافت متن و ترجمه (بخش حساس)
            raw_title = item.title.text
            full_txt = get_full_content(link)
            if not full_txt: 
                full_txt = item.description.text if item.description else "شرحی در دسترس نیست."

            # ترجمه اجباری قبل از ذخیره و ارسال
            title_fa = ai_translate(raw_title)
            desc_fa = ai_translate(full_txt)

            # ذخیره در دیتابیس
            c.execute("INSERT INTO news (title_fa, desc_fa, source, link, pub_date) VALUES (?, ?, ?, ?, ?)",
                      (title_fa, desc_fa, src['name'], link, pub_date_iso))
            news_id = c.lastrowid
            conn.commit()
            
            # ارسال به تلگرام
            send_to_telegram(title_fa, desc_fa, news_id, src['name'], pub_date_iso)
            time.sleep(2) # وقفه بین ارسال‌ها

        conn.close()
    except Exception as e:
        print(f"Error processing {src['name']}: {e}")

# --- زمان‌بندی آپدیت ---
def scheduled_update():
    print(f"Update started at: {datetime.now()}")
    shuffled = SOURCES.copy()
    random.shuffle(shuffled)
    with ThreadPoolExecutor(max_workers=3) as executor:
        executor.map(process_source, shuffled)

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(func=scheduled_update, trigger="interval", minutes=15)
scheduler.start()

# --- مسیرهای فلاسک ---
@app.route('/')
def home():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title_fa, source, pub_date, desc_fa FROM news ORDER BY pub_date DESC LIMIT 50")
    news_list = c.fetchall()
    conn.close()
    return render_template('index.html', news=news_list)

@app.route('/news/<int:news_id>')
def news_detail(news_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT title_fa, desc_fa, source, pub_date, link FROM news WHERE id=?", (news_id,))
    data = c.fetchone()
    conn.close()
    if data:
        return render_template('post.html', title=data[0], content=data[1], source=data[2], date=data[3], original=data[4])
    abort(404)

if __name__ == "__main__":
    # اولین اجرا در ترد جداگانه
    threading.Thread(target=scheduled_update).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))
