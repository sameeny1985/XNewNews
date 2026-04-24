import os
import sqlite3
import requests
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

# لیست کامل منابع (RSS و واسطه‌های توییتر)
SOURCES = [
    {"name": "رویترز", "url": "https://www.reuters.com/arc/outboundfeeds/news-one/?outputType=xml"},
    {"name": "ایران اینترنشنال", "url": "https://www.iranintl.com/rss/all"},
    {"name": "بی بی سی فارسی", "url": "https://www.bbc.com/persian/index.xml"},
    {"name": "رادیو فردا", "url": "https://www.radiofarda.com/api/z$qppe_kq_"},
    {"name": "صدای آمریکا", "url": "https://ir.voanews.com/api/z-m_v_e-it"},
    {"name": "تسنیم", "url": "https://www.tasnimnews.com/fa/rss/feed/0/7/0/"},
    {"name": "دویچه وله", "url": "https://www.dw.com/fa/persian/s-3277"},
    {"name": "آسوشیتدپرس", "url": "https://newsapi.org/v2/everything?q=associated-press&apiKey=YOUR_API_KEY"}, # نیاز به API رایگان newsapi.org دارد
    {"name": "وال استریت ژورنال", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml"},
    {"name": "تایمز اسرائیل", "url": "https://www.timesofisrael.com/feed/"},
    {"name": "جروزالم پست", "url": "https://www.jpost.com/rss/rssfeeds.aspx?catid=1"},
    {"name": "Ynet News", "url": "https://www.ynetnews.com/Ext/App/TalkBack/CdaSampleRSS/0,12870,2,00.xml"},
    {"name": "Israel Hayom", "url": "https://www.israelhayom.com/feed/"},
    {"name": "i24 News", "url": "https://www.i24news.tv/en/rss/main"},
    {"name": "من و تو", "url": "https://www.manototv.com/rss/news"},
    {"name": "کیهان لندن", "url": "https://kayhan.london/fa/feed/"},
    # بخش توییتر (از طریق نایتر Nitter - واسطه رایگان)
    {"name": "توییتر ترامپ", "url": "https://nitter.net/realDonaldTrump/rss"},
    {"name": "توییتر رضا پهلوی", "url": "https://nitter.net/PahlaviReza/rss"},
    {"name": "توییتر نتانیاهو", "url": "https://nitter.net/netanyahu/rss"},
    {"name": "توییتر عراقچی", "url": "https://nitter.net/araghchi/rss"},
    {"name": "توییتر قالیباف", "url": "https://nitter.net/mb_ghalibaf/rss"},
    {"name": "سنتکام", "url": "https://nitter.net/CENTCOM/rss"},
]

def ai_translate(text, src_lang='auto'):
    try:
        if not text or len(text.strip()) < 5: return text
        # پاکسازی تگ‌ها
        clean_input = BeautifulSoup(text, "html.parser").get_text().strip()
        # تشخیص خودکار زبان و ترجمه
        translated = translator.translate(clean_input, dest='fa').text
        return f"\u200f{translated}\u200f"
    except:
        return text

def get_full_content(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        article = Article(url)
        article.config.browser_user_agent = headers['User-Agent']
        article.config.request_timeout = 10
        article.download()
        article.parse()
        if len(article.text) > 150: return article.text
        
        # متد جایگزین (BS4)
        res = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(res.content, "html.parser")
        paragraphs = soup.find_all('p')
        return " ".join([p.get_text() for p in paragraphs if len(p.get_text()) > 60])
    except:
        return ""

def process_single_source(src):
    """پردازش یک منبع به صورت مجزا برای جلوگیری از بلاک شدن کل سیستم"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        res = requests.get(src['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        soup = BeautifulSoup(res.content, "xml")
        time_limit = datetime.now(timezone.utc) - timedelta(hours=12)

        for item in soup.find_all('item')[:3]: # از هر منبع فعلاً ۳ خبر داغ
            link = item.link.text
            try:
                pub_date = parsedate_to_datetime(item.pubDate.text)
            except:
                pub_date = datetime.now(timezone.utc)

            if pub_date < time_limit: continue
            
            c.execute("SELECT id FROM news WHERE link=?", (link,))
            if c.fetchone(): continue

            full_txt = get_full_content(link)
            if not full_txt: full_txt = item.description.text if item.description else ""

            title_fa = ai_translate(item.title.text)
            desc_fa = ai_translate(full_txt)

            c.execute("INSERT INTO news (title_fa, desc_fa, source, link, pub_date) VALUES (?, ?, ?, ?, ?)",
                      (title_fa, desc_fa, src['name'], link, pub_date.isoformat()))
            news_id = c.lastrowid
            conn.commit()
            
            # ارسال تلگرام
            send_to_telegram(title_fa, desc_fa, news_id, src['name'])
        conn.close()
    except Exception as e:
        print(f"Error in {src['name']}: {e}")

def send_to_telegram(title, summary, news_id, source_name):
    if not TOKEN: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    my_link = f"{MY_SITE_URL}/news/{news_id}"
    clean_title = BeautifulSoup(title, "html.parser").get_text()
    clean_summary = BeautifulSoup(summary, "html.parser").get_text()[:300]

    payload = {
        "chat_id": CHAT_ID,
        "text": f"🔴 <b>{clean_title}</b>\n\n🔹 منبع: {source_name}\n📝 {clean_summary}...\n\n🆔 @AnalytixNews",
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": [[{"text": "📖 مطالعه مشروح کامل خبر", "url": my_link}]]}
    }
    requests.post(url, json=payload, timeout=10)

@app.route('/')
def home():
    # استفاده از ThreadPool برای چک کردن همزمان همه منابع (سرعت فوق‌العاده بالا)
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(process_single_source, SOURCES)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title_fa, source, pub_date, desc_fa FROM news ORDER BY pub_date DESC LIMIT 50")
    news_list = c.fetchall()
    conn.close()
    return render_template('index.html', news=news_list)

# بقیه روت‌ها (news_detail و ...) مثل قبل باقی می‌ماند
