import os
import json
import sqlite3
import requests
from flask import Flask, render_template, abort
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from googletrans import Translator
from newspaper import Article

app = Flask(__name__)
translator = Translator()

# --- تنظیمات ---
TOKEN = os.environ.get("TOKEN")
CHAT_ID = "@AnalytixNews"
MY_SITE_URL = "https://irananalysis.onrender.com"
DB_PATH = "news.db"

# کاراکتر کنترلی برای جلوگیری از بهم ریختگی جملات فارسی-انگلیسی
RLM = "\u200f"

def ai_translate(text):
    """ترجمه هوشمند با حفظ چیدمان راست‌به‌چپ"""
    try:
        if not text or len(text.strip()) < 5: return ""
        # ترجمه متن به فارسی
        translated = translator.translate(text, dest='fa').text
        # قرار دادن متن بین دو کاراکتر RLM برای ثبات در تلگرام و وب
        return f"{RLM}{translated}{RLM}"
    except:
        return text

def get_full_content(url):
    """بیرون کشیدن متن کامل خبر از سایت اصلی"""
    try:
        article = Article(url)
        article.download()
        article.parse()
        # برگرداندن متن اصلی (محدود به ۲۰۰۰ کاراکتر برای دیتابیس)
        return article.text[:2000]
    except:
        return ""

def send_to_telegram(title, summary, news_id, source_name):
    """ارسال به تلگرام با دکمه لینک به سایت خودت"""
    if not TOKEN: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    my_link = f"{MY_SITE_URL}/news/{news_id}"
    
    # حذف تگ‌های احتمالی HTML از خلاصه برای جلوگیری از ارور تلگرام
    clean_summary = BeautifulSoup(summary, "html.parser").get_text()[:300]

    message_text = (
        f"🔴 <b>{title}</b>\n\n"
        f"🔹 منبع: {source_name}\n"
        f"📝 {clean_summary}...\n\n"
        f"🆔 @AnalytixNews"
    )
    
    payload = {
        "chat_id": CHAT_ID,
        "text": message_text,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "📖 مطالعه مشروح کامل خبر در سایت", "url": my_link}
            ]]
        }
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def update_news():
    """بروزرسانی اخبار (فیلتر ۱۲ ساعت + جدیدترین در بالا)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS news 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, title_fa TEXT, desc_fa TEXT, 
                  source TEXT, link TEXT UNIQUE, pub_date TIMESTAMP)''')
    
    # بازه زمانی ۱۲ ساعت گذشته
    twelve_hours_ago = datetime.now(timezone.utc) - timedelta(hours=12)
    
    # لیست منابع (RSS)
    SOURCES = [
        {"name": "Reuters", "url": "https://www.reutersagency.com/feed/"},
        {"name": "ایران اینترنشنال", "url": "https://news.google.com/rss/search?q=Iran+International&hl=fa&gl=IR&ceid=IR:fa"}
        # سایر منابع را اینجا اضافه کن...
    ]

    for src in SOURCES:
        try:
            res = requests.get(src['url'], timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
            soup = BeautifulSoup(res.content, "xml")
            items = soup.find_all('item')
            
            for item in items:
                link = item.link.text
                try:
                    pub_date = parsedate_to_datetime(item.pubDate.text)
                except:
                    pub_date = datetime.now(timezone.utc)
                
                # فیلتر ۱۲ ساعت
                if pub_date < twelve_hours_ago: continue
                
                # جلوگیری از تکرار
                c.execute("SELECT id FROM news WHERE link=?", (link,))
                if c.fetchone(): continue
                
                # استخراج متن کامل و ترجمه
                eng_body = get_full_content(link)
                if not eng_body: eng_body = item.description.text if item.description else ""
                
                title_fa = ai_translate(item.title.text)
                desc_fa = ai_translate(eng_body)
                
                c.execute("INSERT INTO news (title_fa, desc_fa, source, link, pub_date) VALUES (?, ?, ?, ?, ?)",
                          (title_fa, desc_fa, src['name'], link, pub_date.isoformat()))
                
                news_id = c.lastrowid
                conn.commit()
                
                # ارسال به تلگرام
                send_to_telegram(title_fa, desc_fa, news_id, src['name'])
        except:
            continue
    conn.close()

@app.route('/')
def home():
    update_news()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # مرتب‌سازی: جدیدترین خبر (DESC) در بالا
    c.execute("SELECT id, title_fa, source, pub_date FROM news ORDER BY pub_date DESC LIMIT 50")
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
