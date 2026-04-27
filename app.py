import os
import time
import sqlite3
import requests
import threading
from flask import Flask, render_template, abort
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from newspaper import Article
from concurrent.futures import ThreadPoolExecutor
import random
from deep_translator import GoogleTranslator
from flask import request
app = Flask(__name__)


TOKEN = os.environ.get("TOKEN")
CHAT_ID = "@XNewNewsMavara"
MY_SITE_URL = "https://voluntary-linn-shapyaar-22266960.koyeb.app/"
DB_PATH = "news.db"

# لیست منابع اصلاح شده برای پایداری
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

from deep_translator import GoogleTranslator

def ai_translate(text):
    try:
        if not text:
            return ""

        clean_text = BeautifulSoup(text, "html.parser").get_text().strip()

        # اگر فارسی بود ترجمه نکن
        if any('\u0600' <= c <= '\u06FF' for c in clean_text[:50]):
            return clean_text

        return GoogleTranslator(source='auto', target='fa').translate(clean_text)

    except:
        return text
def categorize(text):
    text = text.lower()

    if "iran" in text or "tehran" in text:
        return "ایران"
    elif "econom" in text or "market" in text:
        return "اقتصادی"
    elif "war" in text or "military" in text:
        return "سیاسی"
    else:
        return "جهان"
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
        c.execute('''CREATE TABLE IF NOT EXISTS news 
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              title_fa TEXT,
              desc_fa TEXT,
              source TEXT,
              link TEXT UNIQUE,
              pub_date DATETIME,
              category TEXT)''')
        
        res = requests.get(src['url'], headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
        soup = BeautifulSoup(res.content, "xml")
        
        # زمان الان به وقت جهانی (UTC) برای مقایسه دقیق
        now = datetime.now(timezone.utc)
        limit_time = now - timedelta(hours=12)

        for item in soup.find_all('item')[:10]: # بررسی ۱۰ خبر آخر منبع
            link = item.link.text
            
            # --- فیلتر ۱: جلوگیری از تکرار (اگر لینک در دیتابیس هست، برو بعدی) ---
            c.execute("SELECT id FROM news WHERE link=?", (link,))
            if c.fetchone():
                continue

            # --- فیلتر ۲: زمان (فقط ۱۲ ساعت اخیر) ---
            try:
                # تبدیل تاریخ خبر به فرمت پایتون
                pub_date_raw = parsedate_to_datetime(item.pubDate.text)
                # اگر منطقه زمانی نداشت، بهش UTC بده که با 'now' مقایسه بشه
                if pub_date_raw.tzinfo is None:
                    pub_date_raw = pub_date_raw.replace(tzinfo=timezone.utc)
                
                # اگر خبر قدیمی‌تر از ۱۲ ساعت بود، کلاً نادیده بگیر
                if pub_date_raw < (datetime.now(timezone.utc) - timedelta(hours=12)):
                    continue
                
                pub_date_iso = pub_date_raw.strftime('%Y-%m-%d %H:%M:%S')
            except:
                # اگر تاریخ خبر خراب بود، زمان حال رو بزن که بیاد بالای لیست
                pub_date_iso = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # --- عملیات استخراج و ترجمه ---
            full_txt = get_full_content(link)
            if not full_txt: full_txt = item.description.text if item.description else ""

            title_fa = ai_translate(item.title.text)
            desc_fa = ai_translate(full_txt)
            category = categorize(full_txt)
            # ذخیره در دیتابیس
            c.execute("INSERT INTO news (title_fa, desc_fa, source, link, pub_date, category) VALUES (?, ?, ?, ?, ?)",
                      (title_fa, desc_fa, src['name'], link, pub_date_iso, category))
            
            news_id = c.lastrowid
            conn.commit()
            
            # پیدا کن این خط رو در انتهای پردازش هر خبر:
            send_to_telegram(title_fa, desc_fa, news_id, src['name'], pub_date_iso, category)
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
is_updating = False  # این خط باید بیرون از تابع باشد
def categorize(text):
    text = text.lower()

    if "iran" in text or "tehran" in text:
        return "ایران"
    elif "economy" in text or "market" in text:
        return "اقتصادی"
    elif "war" in text or "military" in text:
        return "سیاسی"
    else:
        return "جهان"
@app.route('/')
def home():
    global is_updating
    
    # ۱. بررسی اینکه آیا آپدیت قبلی هنوز در حال اجراست یا نه
    if not is_updating:
        def update_wrapper():
            global is_updating
            is_updating = True
            try:
                # کپی کردن و بُر زدن سورس‌ها برای رعایت عدالت بین منابع!
                shuffled_sources = SOURCES.copy()
                random.shuffle(shuffled_sources)
                
                # اجرای آپدیت با ۸ ورکر (چون پلن پولی داری سرعت رو بردیم بالا)
                with ThreadPoolExecutor(max_workers=8) as executor:
                    executor.map(process_source, shuffled_sources)
            except Exception as e:
                print(f"Update Thread Error: {e}")
            finally:
                is_updating = False
        
        # شروع عملیات در پس‌زمینه
        threading.Thread(target=update_wrapper, daemon=True).start()

    # ۲. بخش نمایش سایت (نمایش اخبار ۱۲ ساعت اخیر با ترتیب جدیدترین)
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        query = """
            SELECT id, title_fa, source, pub_date, desc_fa 
            FROM news 
            WHERE pub_date >= datetime('now', '-12 hours')
            ORDER BY pub_date DESC 
            LIMIT 60
        """
        c.execute(query)
        news_list = c.fetchall()
        conn.close()
        return render_template('index.html', news=news_list)
    except Exception as e:
        return f"Database Error: {e}", 500
def send_to_telegram(title, summary, news_id, source_name, pub_date, category):
    if not TOKEN: return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        # فرمت کردن متن پیام برای نمایش ساعت و تاریخ منبع
        message_text = (
            f"🔴 <b>{title[:200]}</b>\n\n"
            f"📂 دسته: {category}\n"
            f"🔹 منبع: {source_name}\n"
            f"⏰ زمان انتشار منبع: {pub_date}\n"
            f"📝 {summary[:300]}...\n\n"
            f"🆔 @XNewNewsMavara"
        )
        
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message_text,
            "parse_mode": "HTML",
            "reply_markup": {
                "inline_keyboard": [[{"text": "📖 مشاهده کامل", "url": f"{MY_SITE_URL}/news/{news_id}"}]]
            }
        }, timeout=10)
    except:
        pass
import time

def background_updater():
    while True:
        print("🔄 Updating news...")
        try:
            shuffled_sources = SOURCES.copy()
            random.shuffle(shuffled_sources)

            with ThreadPoolExecutor(max_workers=5) as executor:
                executor.map(process_source, shuffled_sources)

        except Exception as e:
            print("Update error:", e)

        time.sleep(300)  # هر 5 دقیقه
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
@app.route('/search')
def search():
    q = request.args.get('q')

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    SELECT id, title_fa, source, pub_date, desc_fa
    FROM news
    WHERE title_fa LIKE ? OR desc_fa LIKE ?
    ORDER BY pub_date DESC
    """, (f"%{q}%", f"%{q}%"))

    news_list = c.fetchall()
    conn.close()

    return render_template('index.html', news=news_list)
def background_updater():
    while True:
        print("🔄 Updating news...")
        try:
            shuffled_sources = SOURCES.copy()
            random.shuffle(shuffled_sources)

            with ThreadPoolExecutor(max_workers=5) as executor:
                executor.map(process_source, shuffled_sources)

        except Exception as e:
            print("Update error:", e)

        time.sleep(300)  # هر 5 دقیقه
if __name__ == "__main__":
    threading.Thread(target=background_updater, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8000)))
