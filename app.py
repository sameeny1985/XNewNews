import os
import sqlite3
import requests
import threading
from flask import Flask, render_template, abort
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from googletrans import Translator
from newspaper import Article
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
translator = Translator()

TOKEN = os.environ.get("TOKEN")
CHAT_ID = "@AnalytixNews"
MY_SITE_URL = "https://fxanlytix-news-np0s.onrender.com"
DB_PATH = "news.db"

# لیست منابع اصلاح شده برای پایداری
SOURCES = [
    {"name": "رویترز", "url": "https://www.reuters.com/arc/outboundfeeds/news-one/?outputType=xml"},
    {"name": "ایران اینترنشنال", "url": "https://www.iranintl.com/rss/all"},
    {"name": "بی بی سی فارسی", "url": "https://www.bbc.com/persian/index.xml"},
    {"name": "رادیو فردا", "url": "https://www.radiofarda.com/api/z$qppe_kq_"},
    {"name": "صدای آمریکا", "url": "https://ir.voanews.com/api/z-m_v_e-it"},
    {"name": "تسنیم", "url": "https://www.tasnimnews.com/fa/rss/feed/0/7/0/"},
    {"name": "دویچه وله", "url": "https://www.dw.com/fa/persian/s-3277"},
    {"name": "تایمز اسرائیل", "url": "https://www.timesofisrael.com/feed/"},
    {"name": "جروزالم پست", "url": "https://www.jpost.com/rss/rssfeeds.aspx?catid=1"},
    {"name": "توییتر ترامپ", "url": "https://nitter.net/realDonaldTrump/rss"},
    {"name": "توییتر نتانیاهو", "url": "https://nitter.net/netanyahu/rss"},
    {"name": "توییتر رضا پهلوی", "url": "https://nitter.net/PahlaviReza/rss"}
]

def ai_translate(text):
    try:
        if not text: return ""
        clean_input = BeautifulSoup(text, "html.parser").get_text().strip()
        if any('\u0600' <= char <= '\u06FF' for char in clean_input[:30]):
            return f"\u200f{clean_input}\u200f"
        return f"\u200f{translator.translate(clean_input, dest='fa').text}\u200f"
    except:
        return text

def get_full_content(url):
    try:
        article = Article(url)
        article.config.browser_user_agent = 'Mozilla/5.0'
        article.config.request_timeout = 10
        article.download(); article.parse()
        return article.text if len(article.text) > 100 else ""
    except:
        return ""

def process_source(src):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # اطمینان از وجود جدول با فیلد زمان
        c.execute('''CREATE TABLE IF NOT EXISTS news 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, title_fa TEXT, desc_fa TEXT, 
                      source TEXT, link TEXT UNIQUE, pub_date DATETIME)''')
        
        res = requests.get(src['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        soup = BeautifulSoup(res.content, "xml")
        
        for item in soup.find_all('item')[:5]: # بررسی ۵ خبر آخر هر منبع
            link = item.link.text
            
            # استخراج زمان واقعی انتشار خبر
            try:
                pub_date_raw = parsedate_to_datetime(item.pubDate.text)
                # تبدیل به فرمت قابل فهم برای دیتابیس (ISO format)
                pub_date_iso = pub_date_raw.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pub_date_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            c.execute("SELECT id FROM news WHERE link=?", (link,))
            if c.fetchone(): continue

            full_txt = get_full_content(link)
            if not full_txt: full_txt = item.description.text if item.description else ""

            title_fa = ai_translate(item.title.text)
            desc_fa = ai_translate(full_txt)

            # ذخیره با زمان واقعی انتشار
            c.execute("INSERT INTO news (title_fa, desc_fa, source, link, pub_date) VALUES (?, ?, ?, ?, ?)",
                      (title_fa, desc_fa, src['name'], link, pub_date_iso))
            
            news_id = c.lastrowid
            conn.commit()
            
            # ارسال به تلگرام (به محض پیدا شدن خبر جدید)
            send_to_telegram(title_fa, desc_fa, news_id, src['name'])
        conn.close()
    except:
        pass

@app.route('/')
def home():
    # آپدیت در پس‌زمینه
    threading.Thread(target=lambda: ThreadPoolExecutor(max_workers=4).map(process_source, SOURCES)).start()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # مرتب‌سازی بر اساس زمان انتشار (جدیدترین در بالای سایت)
    c.execute("SELECT id, title_fa, source, pub_date, desc_fa FROM news ORDER BY pub_date DESC LIMIT 60")
    news_list = c.fetchall()
    conn.close()
    return render_template('index.html', news=news_list)
def send_to_telegram(title, summary, news_id, source_name):
    if not TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": f"🔴 <b>{title[:200]}</b>\n\n🔹 منبع: {source_name}\n📝 {summary[:300]}...\n\n🆔 @AnalytixNews",
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": [[{"text": "📖 مشاهده کامل", "url": f"{MY_SITE_URL}/news/{news_id}"}]]}
        }, timeout=10)
    except:
        pass
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
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
