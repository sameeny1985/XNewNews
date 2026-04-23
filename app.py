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
TOKEN = "8794841888:AAEp8OscKwCmIHxujIQHG4-yyju5wPV7u2k"
CHAT_ID = "@AnalytixNews"
MY_SITE_URL = "https://irananalysis.onrender.com"
DB_PATH = "news.db"

# نشانه RLM برای جلوگیری از بهم ریختگی متن در فارسی و انگلیسی
RLM = "\u200f"

def ai_translate(text):
    """ترجمه با تلاش برای حفظ ساختار جملات فارسی"""
    try:
        if not text or len(text) < 5: return ""
        # ترجمه توسط هوش مصنوعی گوگل (نسخه جدید)
        result = translator.translate(text, dest='fa')
        translated_text = result.text
        # اضافه کردن کاراکتر کنترل جهت برای جلوگیری از بهم ریختگی کلمات انگلیسی لابلای فارسی
        return f"{RLM}{translated_text}"
    except:
        return text

def get_full_content(url):
    """استخراج هوشمند متن کامل مقاله از سایت منبع"""
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text
    except:
        return ""

def send_to_telegram(title, summary, news_id, source_name):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    my_link = f"{MY_SITE_URL}/news/{news_id}"
    
    # متنی که در تلگرام نمایش داده می‌شود
    message_text = (
        f"🔴 <b>{title}</b>\n\n"
        f"🔹 منبع: {source_name}\n"
        f"📝 {summary[:300]}...\n\n"
        f"🆔 @AnalytixNews"
    )
    
    payload = {
        "chat_id": CHAT_ID,
        "text": message_text,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [[
                {"text": "مشاهده شرح کامل در سایت من", "url": my_link}
            ]]
        }
    }
    requests.post(url, json=payload)

def update_news():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # ایجاد دیتابیس اگر وجود ندارد
    c.execute('''CREATE TABLE IF NOT EXISTS news (id INTEGER PRIMARY KEY AUTOINCREMENT, title_fa TEXT, desc_fa TEXT, source TEXT, link UNIQUE, pub_date TIMESTAMP)''')
    
    twelve_hours_ago = datetime.now(timezone.utc) - timedelta(hours=12)
    
    # در اینجا فقط چند منبع برای نمونه گذاشتم، لیست کامل خودت رو اضافه کن
    SOURCES = [{"name": "Reuters", "url": "https://www.reutersagency.com/feed/"}] 

    for src in SOURCES:
        try:
            res = requests.get(src['url'], timeout=15)
            soup = BeautifulSoup(res.content, "xml")
            items = soup.find_all('item')
            
            for item in items:
                link = item.link.text
                pub_date = parsedate_to_datetime(item.pubDate.text)
                
                if pub_date < twelve_hours_ago: continue
                
                c.execute("SELECT id FROM news WHERE link=?", (link,))
                if c.fetchone(): continue
                
                # استخراج و ترجمه
                full_eng_text = get_full_content(link)
                title_fa = ai_translate(item.title.text)
                desc_fa = ai_translate(full_eng_text if full_eng_text else item.description.text)
                
                c.execute("INSERT INTO news (title_fa, desc_fa, source, link, pub_date) VALUES (?, ?, ?, ?, ?)",
                          (title_fa, desc_fa, src['name'], link, pub_date))
                
                news_id = c.lastrowid
                conn.commit()
                send_to_telegram(title_fa, desc_fa, news_id, src['name'])
        except: continue
    conn.close()

@app.route('/')
def home():
    update_news() # هر بار سایت باز بشه چک میکنه
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title_fa, source, pub_date FROM news ORDER BY pub_date DESC")
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
    app.run(host='0.0.0.0', port=5000)
