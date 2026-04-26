import os
import sqlite3
import requests
import random
import threading
from flask import Flask, render_template, abort
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from googletrans import Translator
from newspaper import Article
from concurrent.futures import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
import subprocess
import sys


app = Flask(__name__)
translator = Translator()

# تنظیمات اصلی از محیط کویب
TOKEN = os.environ.get("TOKEN")
CHAT_ID = "@XNewNewsMavara"
MY_SITE_URL = "https://voluntary-linn-shapyaar-22266960.koyeb.app/"
DB_PATH = "news.db"

# لیست منابع (RSS و Nitter)
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

    # --- منابع اسرائیلی ---
    {"name": "رادیو پیام اسرائیل", "url": "https://radisrael.com/feed/"},
    {"name": "کانال ۱۱ اسرائیل (Kaan)", "url": "https://www.kan.org.il/rss/"},
    {"name": "کانال ۱۲ اسرائیل (N12)", "url": "https://www.mako.co.il/news-israel?partner=rss"},
    {"name": "کانال ۱۴ اسرائیل", "url": "https://www.now14.co.il/feed/"},

    # --- توییترها (از طریق Nitter برای دور زدن فیلتر کویب) ---
    {"name": "توییتر ترامپ", "url": "https://nitter.net/realDonaldTrump/rss"},
    {"name": "توییتر نتانیاهو", "url": "https://nitter.net/netanyahu/rss"},
    {"name": "توییتر رضا پهلوی", "url": "https://nitter.net/PahlaviReza/rss"},
    {"name": "سخنگوی کاخ سفید", "url": "https://nitter.net/PressSec/rss"},
    {"name": "خبرگزاری تسنیم", "url": "https://www.tasnimnews.com/fa/rss/allfeed"},
    {"name": "خبرگزاری ایسنا (ISNA)", "url": "https://www.isna.ir/rss"},
    {"name": "تایمز اسرائیل (فارسی)", "url": "https://fa.timesofisrael.com/feed/"},
    {"name": "وزیر دفاع اسرائیل", "url": "https://nitter.net/YoavGallant/rss"},
    {"name": "آسوشیتد پرس (AP)", "url": "https://news.google.com/rss/search?q=source:Associated+Press&hl=en&gl=US&ceid=US:en"},
    #{"name": "الجزیره (انگلیسی)", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    #{"name": "العربیه (فارسی)", "url": "https://farsi.alarabiya.net/.mrss/fa.xml"},
    {"name": "توییتر عباس عراقچی", "url": "https://nitter.net/araghchi/rss"},
    {"name": "توییتر قالیباف", "url": "https://nitter.net/mb_ghalibaf/rss"},
    {"name": "سناتور لیندسی گراهام", "url": "https://nitter.net/LindseyGrahamSC/rss"},
    {"name": "وزیر دفاع آمریکا", "url": "https://nitter.net/SecDef/rss"},
    {"name": "سخنگوی سنتکام (CENTCOM)", "url": "https://nitter.net/CENTCOM/rss"},
    {"name": "من و تو (Manoto)", "url": "https://news.google.com/rss/search?q=source:Manoto&hl=fa&gl=IR&ceid=IR:fa"},
    {"name": "کیهان لندن", "url": "https://kayhan.london/fa/feed/"},
    #{"name": "توییتر محسن رضایی", "url": "https://nitter.net/ir_rezaee/rss"},
    #{"name": "دبیرکل سازمان ملل (Guterres)", "url": "https://nitter.net/antonioguterres/rss"},
    #{"name": "سخنگوی سازمان ملل", "url": "https://nitter.net/UN_Spokesperson/rss"},
    #{"name": "نیکی هیلی (Nikki Haley)", "url": "https://nitter.net/NikkiHaley/rss"},
    {"name": "سخنگوی شورای امنیت ملی آمریکا", "url": "https://nitter.net/NSC_Spox/rss"},
    #{"name": "سخنگوی عفو بین‌الملل", "url": "https://nitter.net/AgnesCallamard/rss"},
    {"name": "وال استریت ژورنال (WSJ)", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml"},
    {"name": "صدای آمریکا (VOA)", "url": "https://nitter.net/VOAIran/rss"},
    {"name": "رادیو فردا", "url": "https://nitter.net/RadioFarda_/rss"},
    {"name": "من و تو (Manoto)", "url": "https://nitter.net/manototv/rss"},
    {"name": "رویترز (Reuters Iran)", "url": "https://nitter.net/ReutersIran/rss"},
    {"name": "دویچه وله (DW) فارسی", "url": "https://nitter.net/dw_persian/rss"},
    # {"name": "خبرگزاری فارس", "url": "https://nitter.net/FarsNews_Agency/rss"},
    # {"name": "خبرگزاری تسنیم", "url": "https://nitter.net/Tasnimnews_Fa/rss"},
    # {"name": "خبرگزاری ایسنا", "url": "https://nitter.net/isna_farsi/rss"},
    #{"name": "العربیه فارسی", "url": "https://nitter.net/AlArabiya_Far/rss"},
    #{"name": "کیهان لندن", "url": "https://nitter.net/KayhanLondon/rss"},
    #{"name": "وال استریت ژورنال", "url": "https://nitter.net/WSJ/rss"},
    
    # --- منابع اسرائیلی (نسخه توییتر برای پایداری ۱۰۰٪) ---
    #{"name": "کانال ۱۱ اسرائیل (Kaan)", "url": "https://nitter.net/kann_news/rss"},
    #{"name": "کانال ۱۲ اسرائیل (N12)", "url": "https://nitter.net/N12News/rss"},
    #{"name": "کانال ۱۴ اسرائیل", "url": "https://nitter.net/Now14Israel/rss"},
    #{"name": "تایمز اسرائیل (فارسی)", "url": "https://nitter.net/TimesofIsraelFA/rss"},
    #{"name": "رادیو پیام اسرائیل", "url": "https://nitter.net/Be_Yisrael/rss"},
    {"name": "تحلیل استراتژیک ویدکاف", "url": "https://nitter.cz/vidcaff/rss"},
    {"name": "i24News English", "url": "https://nitter.net/i24NEWS_EN/rss"},
    {"name": "Jerusalem Post", "url": "https://nitter.net/Jerusalem_Post/rss"},
    {"name": "Times of Israel", "url": "https://nitter.net/TimesofIsrael/rss"},
    {"name": "Ynet News", "url": "https://nitter.net/ynetnews/rss"},
    {"name": "Israel Hayom", "url": "https://nitter.net/IsraelHayomEng/rss"}
]

import translators as ts
import time

def ai_translate(text):
    if not text or len(text.strip()) < 5: 
        return text
    
    try:
        # ۱. تمیز کردن متن از فاصله‌های اضافی
        clean_text = BeautifulSoup(text, "html.parser").get_text().strip()

        # ۲. بررسی هوشمندتر: فقط اگه بیش از ۵۰٪ متن فارسی بود ترجمه نکن
        # اینطوری اگه اول متن انگلیسی دوتا کلمه فارسی هم باشه، باز ترجمه انجام میشه
        farsi_chars = sum(1 for char in clean_text[:50] if '\u0600' <= char <= '\u06FF')
        if farsi_chars > (len(clean_text[:50]) / 2):
            return f"\u200f{clean_text}\u200f"

        # ۳. وقفه کوتاه برای دور زدن سیستم امنیتی مترجم
        time.sleep(1)

        # ۴. استفاده از موتور گوگل از طریق کتابخانه جدید (پایدارتر از قبلی)
        # اگه bing اذیت میکرد، اینجا از 'google' استفاده کن
        translated = ts.translate_text(clean_text, from_language='auto', to_language='fa', engine='google')
        
        return f"\u200f{translated}\u200f"

    except Exception as e:
        # ۵. اینجا مچ کد رو میگیریم؛ اگه ترجمه نشد یه علامت بذار که بفهمی ارور داده
        print(f"!!! Translation Failed: {e}")
        return f"[ترجمه نشده]: {text}"
def get_full_content(url):
    try:
        article = Article(url)
        article.config.browser_user_agent = 'Mozilla/5.0'
        article.download()
        article.parse()
        return article.text if len(article.text) > 100 else ""
    except: return ""

def send_to_telegram(title, summary, news_id, source_name, pub_date):
    if not TOKEN: return
    try:
        # این دو خط پایین جادوی اصلیه؛ متن انگلیسی رو میگیره و فارسی میکنه
        farsi_title = ai_translate(title)
        farsi_summary = ai_translate(summary)
        
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        
        # اینجا از متن‌های فارسی شده (farsi_title و farsi_summary) استفاده می‌کنیم
        message_text = (
            f"🔴 <b>{farsi_title}</b>\n\n"
            f"🔹 منبع: {source_name}\n"
            f"⏰ زمان: {pub_date}\n"
            f"📝 {farsi_summary[:400]}...\n\n"
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
        
        # ارسال نهایی به تلگرام
        requests.post(url, json=payload, timeout=12)
        
    except Exception as e:
        print(f"خطا در ارسال تلگرام: {e}")
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

            full_txt = get_full_content(link)
            if not full_txt: 
                full_txt = item.description.text if item.description else "شرحی در دسترس نیست."

            title_fa = ai_translate(item.title.text)
            desc_fa = ai_translate(full_txt)

            c.execute("INSERT INTO news (title_fa, desc_fa, source, link, pub_date) VALUES (?, ?, ?, ?, ?)",
                      (title_fa, desc_fa, src['name'], link, pub_date_iso))
            news_id = c.lastrowid
            conn.commit()
            
            send_to_telegram(title_fa, desc_fa, news_id, src['name'], pub_date_iso)
        conn.close()
    except: pass

def scheduled_update():
    print(f"شروع آپدیت خودکار... {datetime.now()}")
    shuffled = SOURCES.copy()
    random.shuffle(shuffled)
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(process_source, shuffled)

# تنظیم Scheduler برای اجرای هر 10 دقیقه
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(func=scheduled_update, trigger="interval", minutes=10)
scheduler.start()

@app.route('/')
def home():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title_fa, source, pub_date, desc_fa FROM news WHERE pub_date >= datetime('now', '-12 hours') ORDER BY pub_date DESC LIMIT 60")
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
    # اجرای اولین آپدیت به محض روشن شدن سرور
    threading.Thread(target=scheduled_update).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))
