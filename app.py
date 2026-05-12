import os
import sqlite3
import requests
import random
import time
import threading
from flask import Flask, render_template, abort
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from googletrans import Translator
from newspaper import Article
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
translator = Translator()

# تنظیمات اصلی
TOKEN = os.environ.get("TOKEN")
CHAT_ID = "@XNewNewsMavara"
MY_SITE_URL = "https://voluntary-linn-shapyaar-22266960.koyeb.app"
DB_PATH = "news.db"

SOURCES = [
    #{"name": "رویترز", "url": "https://www.reuters.com/arc/outboundfeeds/news-one/?outputType=xml"},
    {"name": "ایران اینترنشنال", "url": "https://www.iranintl.com/rss/all"},
    {"name": "بی بی سی فارسی", "url": "https://www.bbc.com/persian/index.xml"},
    #{"name": "رادیو فردا", "url": "https://www.radiofarda.com/api/z$qppe_kq_"},
    #{"name": "صدای آمریکا", "url": "https://ir.voanews.com/api/z-m_v_e-it"},
    #{"name": "تسنیم", "url": "https://www.tasnimnews.com/fa/rss/feed/0/7/0/"},
    {"name": "دویچه وله", "url": "https://www.dw.com/fa/persian/s-3277"},
    {"name": "تایمز اسرائیل", "url": "https://www.timesofisrael.com/feed/"},
    {"name": "جروزالم پست", "url": "https://www.jpost.com/rss/rssfeeds.aspx?catid=1"},
    {"name": "توییتر ترامپ", "url": "https://nitter.net/realDonaldTrump/rss"},
    {"name": "توییتر نتانیاهو", "url": "https://nitter.net/netanyahu/rss"},
    {"name": "توییتر رضا پهلوی", "url": "https://nitter.net/PahlaviReza/rss"},
    #{"name": "ایران اینترنشنال", "url": "https://news.google.com/rss/search?q=Iran+International&hl=fa&gl=IR&ceid=IR:fa"},
    #{"name": "صدای آمریکا (VOA)", "url": "https://ir.voanews.com/api/z$p_eyuvt_"},
    {"name": "رادیو فردا", "url": "https://www.radiofarda.com/api/zsqym_egiv"},
    #{"name": "بی‌بی‌سی فارسی", "url": "https://www.bbc.com/persian/index.xml"},
    #{"name": "دویچه وله (DW)", "url": "https://rss.dw.com/rdf/rss-fa-all"},
    #{"name": "خبرگزاری فارس", "url": "https://www.farsnews.ir/rss"},
   
    {"name": "رویترز (Reuters)", "url": "https://www.reutersagency.com/feed/"},
    {"name": "CNN (Iran Focus)", "url": "https://news.google.com/rss/search?q=CNN+Iran&hl=en&gl=US&ceid=US:en"},
    {"name": "Fox News (Iran Focus)", "url": "https://news.google.com/rss/search?q=Fox+News+Iran&hl=en&gl=US&ceid=US:en"},

    # --- منابع اسرائیلی ---
    {"name": "رادیو پیام اسرائیل", "url": "https://radisrael.com/feed/"},
    {"name": "کانال ۱۱ اسرائیل (Kaan)", "url": "https://www.kan.org.il/rss/"},
    {"name": "کانال ۱۲ اسرائیل (N12)", "url": "https://www.mako.co.il/news-israel?partner=rss"},
    {"name": "کانال ۱۴ اسرائیل", "url": "https://www.now14.co.il/feed/"},

    # --- توییترها (از طریق Nitter برای دور زدن فیلتر کویب) ---
    #{"name": "توییتر ترامپ", "url": "https://nitter.net/realDonaldTrump/rss"},
    #{"name": "توییتر نتانیاهو", "url": "https://nitter.net/netanyahu/rss"},
    #{"name": "توییتر رضا پهلوی", "url": "https://nitter.net/PahlaviReza/rss"},
    {"name": "سخنگوی کاخ سفید", "url": "https://nitter.net/PressSec/rss"},
    #{"name": "خبرگزاری تسنیم", "url": "https://www.tasnimnews.com/fa/rss/allfeed"},
    #{"name": "خبرگزاری ایسنا (ISNA)", "url": "https://www.isna.ir/rss"},
    #{"name": "تایمز اسرائیل (فارسی)", "url": "https://fa.timesofisrael.com/feed/"},
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
    #{"name": "سخنگوی شورای امنیت ملی آمریکا", "url": "https://nitter.net/NSC_Spox/rss"},
    #{"name": "سخنگوی عفو بین‌الملل", "url": "https://nitter.net/AgnesCallamard/rss"},
    {"name": "وال استریت ژورنال (WSJ)", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml"},
    {"name": "صدای آمریکا (VOA)", "url": "https://nitter.net/VOAIran/rss"},
    #{"name": "رادیو فردا", "url": "https://nitter.net/RadioFarda_/rss"},
    #{"name": "من و تو (Manoto)", "url": "https://nitter.net/manototv/rss"},
    #{"name": "رویترز (Reuters Iran)", "url": "https://nitter.net/ReutersIran/rss"},
    #{"name": "دویچه وله (DW) فارسی", "url": "https://nitter.net/dw_persian/rss"},
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

def ai_translate(text):
    try:
        if not text: return ""
        clean_input = BeautifulSoup(text, "html.parser").get_text().strip()
        if any('\u0600' <= char <= '\u06FF' for char in clean_input[:30]):
            return f"\u200f{clean_input}\u200f"
        return f"\u200f{translator.translate(clean_input, dest='fa').text}\u200f"
    except: return text

def send_to_telegram(title, summary, news_id, source_name):
    if not TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        message_text = (
            f"🔴 <b>{title[:200]}</b>\n\n"
            f"🔹 منبع: {source_name}\n"
            f"📝 {summary[:300]}...\n\n"
            f"🆔 @XNewNewsMavara"
        )
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message_text,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [[{"text": "📖 مشاهده در سایت", "url": f"{MY_SITE_URL}/news/{news_id}"}]]
            }
        }, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

def process_source(src):
    try:
        conn = sqlite3.connect(DB_PATH)# این خط را اضافه کن:
        #conn.row_factory = sqlite3.Row 
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS news (id INTEGER PRIMARY KEY AUTOINCREMENT, title_fa TEXT, desc_fa TEXT, source TEXT, link TEXT UNIQUE, pub_date DATETIME)''')
        
        res = requests.get(src['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        soup = BeautifulSoup(res.content, "xml")
        
        for item in soup.find_all('item')[:5]:
            link = item.link.text
            c.execute("SELECT id FROM news WHERE link=?", (link,))
            if c.fetchone(): continue
            
            try:
                article = Article(link)
                article.download()
                article.parse()
                raw_text = article.text[:2000]
            except:
                raw_text = item.description.text if item.description else "خلاصه در سایت موجود است."
            
            # --- تغییر اینجاست ---
            raw_title = item.title.text
            short_title = raw_title[:200] + "..." if len(raw_title) > 200 else raw_title
            title_fa = ai_translate(short_title)
            # ----------------------

            desc_fa = ai_translate(raw_text)
            pub_date_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            c.execute("INSERT INTO news (title_fa, desc_fa, source, link, pub_date) VALUES (?, ?, ?, ?, ?)", 
                      (title_fa, desc_fa, src['name'], link, pub_date_iso))
            news_id = c.lastrowid
            conn.commit()
            
            # ارسال همزمان به تلگرام
            send_to_telegram(title_fa, desc_fa, news_id, src['name'])
            
        conn.close()
    except Exception as e:
        print(f"Source Error ({src['name']}): {e}")

def run_update_cycle():
    """این تابع هم سایت و هم تلگرام رو آپدیت می‌کنه"""
    shuffled = SOURCES.copy()
    random.shuffle(shuffled)
    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(process_source, shuffled)

@app.route('/')
def home():
    threading.Thread(target=run_update_cycle).start()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # <--- این خط جادویی را دقیقاً اینجا بگذار
    c = conn.cursor()
    c.execute("SELECT id, title_fa, source, pub_date, desc_fa FROM news ORDER BY pub_date DESC LIMIT 60")
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
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))
