import os
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

TOKEN = os.environ.get("TOKEN")
CHAT_ID = "@AnalytixNews"
MY_SITE_URL = "https://fxanlytix-news-np0s.onrender.com"
DB_PATH = "news.db"

def ai_translate(text):
    """ترجمه هوشمند با حذف تگ‌های مخرب"""
    try:
        if not text: return ""
        # پاکسازی متن از کدهای HTML که در عکس قبلی بود
        clean_input = BeautifulSoup(text, "html.parser").get_text()
        if len(clean_input.strip()) < 5: return clean_input
        
        translated = translator.translate(clean_input, dest='fa').text
        return f"\u200f{translated}\u200f"
    except Exception as e:
        print(f"Translation Error: {e}")
        return text # اگر ترجمه نشد، اصل متن رو برگردون که برنامه متوقف نشه

def get_full_content(url):
    try:
        article = Article(url)
        article.config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        article.config.request_timeout = 15
        article.download()
        article.parse()
        return article.text[:3000]
    except:
        return ""

def send_to_telegram(title, summary, news_id, source_name):
    if not TOKEN: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    my_link = f"{MY_SITE_URL}/news/{news_id}"
    
    # اطمینان از اینکه هیچ کد HTML مخربی به تلگرام ارسال نمیشه
    clean_title = BeautifulSoup(title, "html.parser").get_text()
    clean_summary = BeautifulSoup(summary, "html.parser").get_text()[:250]

    message_text = (
        f"🔴 <b>{clean_title}</b>\n\n"
        f"🔹 منبع: {source_name}\n"
        f"📝 {clean_summary}...\n\n"
        f"🆔 @AnalytixNews"
    )
    
    payload = {
        "chat_id": CHAT_ID,
        "text": message_text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": [[{"text": "📖 مطالعه مشروح کامل در سایت", "url": my_link}]]}
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def update_news():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS news (id INTEGER PRIMARY KEY AUTOINCREMENT, title_fa TEXT, desc_fa TEXT, source TEXT, link TEXT UNIQUE, pub_date TIMESTAMP)''')
    
    # برای تست، بازه رو به ۴۸ ساعت تغییر دادم که حتماً خبر پیدا کنه
    time_limit = datetime.now(timezone.utc) - timedelta(hours=48)
    
    # استفاده از منابع معتبرتر که کمتر مسدود می‌کنند
    SOURCES = [
        {"name": "رویترز", "url": "https://www.reutersagency.com/feed/"},
        {"name": "تابناک", "url": "https://www.tabnak.ir/fa/rss/allnews"},
        {"name": "ایران اینترنشنال", "url": "https://news.google.com/rss/search?q=Iran+International&hl=fa&gl=IR&ceid=IR:fa"}
    ]

    for src in SOURCES:
        try:
            # اضافه کردن هدر برای دور زدن محدودیت سایت‌ها
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(src['url'], headers=headers, timeout=20)
            soup = BeautifulSoup(res.content, "xml")
            
            for item in soup.find_all('item')[:5]:
                link = item.link.text
                try:
                    pub_date = parsedate_to_datetime(item.pubDate.text)
                except:
                    pub_date = datetime.now(timezone.utc)
                
                if pub_date < time_limit: continue
                
                c.execute("SELECT id FROM news WHERE link=?", (link,))
                if c.fetchone(): continue
                
                full_txt = get_full_content(link)
                if not full_txt: full_txt = item.description.text if item.description else "شرحی یافت نشد"
                
                title_fa = ai_translate(item.title.text)
                desc_fa = ai_translate(full_txt)
                
                c.execute("INSERT INTO news (title_fa, desc_fa, source, link, pub_date) VALUES (?, ?, ?, ?, ?)",
                          (title_fa, desc_fa, src['name'], link, pub_date.isoformat()))
                news_id = c.lastrowid
                conn.commit()
                
                send_to_telegram(title_fa, desc_fa, news_id, src['name'])
        except Exception as e:
            print(f"Error in source {src['name']}: {e}")
            continue
    conn.close()

@app.route('/')
def home():
    try:
        update_news()
    except Exception as e:
        print(f"Update Loop Error: {e}")
        
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
