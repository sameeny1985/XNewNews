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

# --- تنظیمات کلیدی ---
TOKEN = os.environ.get("TOKEN")
CHAT_ID = "@AnalytixNews"
# حتماً آدرس سایتت رو چک کن که آخرش اسلش اضافه نداشته باشه
MY_SITE_URL = "https://irananalysis.onrender.com"
DB_PATH = "news.db"
RLM = "\u200f" # برای جلوگیری از بهم ریختگی متن

def ai_translate(text):
    try:
        if not text or len(text.strip()) < 5: return ""
        # ابتدا هر چی تگ HTML هست رو پاک می‌کنیم که کدها ترجمه نشن
        clean_text = BeautifulSoup(text, "html.parser").get_text()
        translated = translator.translate(clean_text, dest='fa').text
        # استفاده از RLM برای فیکس کردن جهت متن
        return f"\u200f{translated}\u200f"
    except:
        return text

def get_full_content(url):
    try:
        article = Article(url)
        # تنظیم User-Agent برای اینکه سایت‌ها ما رو مسدود نکنن
        article.config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        article.download()
        article.parse()
        # فقط متن تمیز رو برمی‌گردونیم
        return article.text
    except Exception as e:
        print(f"Error extracting content: {e}")
        return ""

def send_to_telegram(title, summary, news_id, source_name):
   # پاکسازی نهایی برای تلگرام
    title = BeautifulSoup(title, "html.parser").get_text()
    summary = BeautifulSoup(summary, "html.parser").get_text()[:300] 
    if not TOKEN: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    
    # اصلاح لینک: باید دقیقاً با روت /news/<id> یکی باشه
    my_link = f"{MY_SITE_URL}/news/{news_id}"
    
    message_text = (
        f"🔴 <b>{title}</b>\n\n"
        f"🔹 منبع: {source_name}\n"
        f"📝 {summary[:250]}...\n\n"
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
    requests.post(url, json=payload, timeout=10)

def update_news():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS news 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, title_fa TEXT, desc_fa TEXT, 
                  source TEXT, link TEXT UNIQUE, pub_date TIMESTAMP)''')
    
    twelve_hours_ago = datetime.now(timezone.utc) - timedelta(hours=12)
    
    SOURCES = [
        {"name": "Reuters", "url": "https://www.reutersagency.com/feed/"},
        {"name": "ایران اینترنشنال", "url": "https://news.google.com/rss/search?q=Iran+International&hl=fa&gl=IR&ceid=IR:fa"},
        {"name": "BBC Persian", "url": "https://www.bbc.com/persian/index.xml"}
    ]

    for src in SOURCES:
        try:
            res = requests.get(src['url'], timeout=15)
            soup = BeautifulSoup(res.content, "xml")
            for item in soup.find_all('item')[:5]:
                link = item.link.text
                pub_date = parsedate_to_datetime(item.pubDate.text)
                
                if pub_date < twelve_hours_ago: continue
                
                c.execute("SELECT id FROM news WHERE link=?", (link,))
                if c.fetchone(): continue
                
                # استخراج شرح کامل
                eng_body = get_full_content(link)
                if not eng_body: eng_body = item.description.text if item.description else ""
                
                title_fa = ai_translate(item.title.text)
                desc_fa = ai_translate(eng_body)
                
                # ذخیره در دیتابیس
                c.execute("INSERT INTO news (title_fa, desc_fa, source, link, pub_date) VALUES (?, ?, ?, ?, ?)",
                          (title_fa, desc_fa, src['name'], link, pub_date.isoformat()))
                
                news_id = c.lastrowid # گرفتن آی‌دی دقیق برای لینک تلگرام
                conn.commit() # حتماً اینجا کامیت بشه تا لینک تلگرام کار کنه
                
                send_to_telegram(title_fa, desc_fa, news_id, src['name'])
        except: continue
    conn.close()

@app.route('/')
def home():
    update_news()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # اینجا desc_fa رو هم اضافه کردم تا در صفحه اصلی توضیح باشه
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
        # نمایش شرح کامل ترجمه شده
        return render_template('post.html', title=data[0], content=data[1], source=data[2], date=data[3], original=data[4])
    else:
        return "<h1>خبر پیدا نشد! احتمالاً دیتابیس ریست شده است.</h1>", 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
