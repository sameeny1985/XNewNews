import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template
import sqlite3
import os
import time
from email.utils import parsedate_to_datetime

app = Flask(__name__)

# --- تنظیمات ---
TOKEN = "8794841888:AAEp8OscKwCmIHxujIQHG4-yyju5wPV7u2k"
CHAT_ID = "@AnalytixNews"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "news.db")

SOURCES = [
    # --- منابع فارسی و بین‌المللی ---
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
    {"name": "الجزیره (انگلیسی)", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"name": "العربیه (فارسی)", "url": "https://farsi.alarabiya.net/.mrss/fa.xml"},
    {"name": "توییتر عباس عراقچی", "url": "https://nitter.net/araghchi/rss"},
    {"name": "توییتر قالیباف", "url": "https://nitter.net/mb_ghalibaf/rss"},
    {"name": "سناتور لیندسی گراهام", "url": "https://nitter.net/LindseyGrahamSC/rss"},
    {"name": "وزیر دفاع آمریکا", "url": "https://nitter.net/SecDef/rss"},
    {"name": "سخنگوی سنتکام (CENTCOM)", "url": "https://nitter.net/CENTCOM/rss"},
    {"name": "من و تو (Manoto)", "url": "https://news.google.com/rss/search?q=source:Manoto&hl=fa&gl=IR&ceid=IR:fa"},
    {"name": "کیهان لندن", "url": "https://kayhan.london/fa/feed/"},
    {"name": "توییتر محسن رضایی", "url": "https://nitter.net/ir_rezaee/rss"},
    {"name": "دبیرکل سازمان ملل (Guterres)", "url": "https://nitter.net/antonioguterres/rss"},
    {"name": "سخنگوی سازمان ملل", "url": "https://nitter.net/UN_Spokesperson/rss"},
    {"name": "نیکی هیلی (Nikki Haley)", "url": "https://nitter.net/NikkiHaley/rss"},
    {"name": "سخنگوی شورای امنیت ملی آمریکا", "url": "https://nitter.net/NSC_Spox/rss"},
    {"name": "سخنگوی عفو بین‌الملل", "url": "https://nitter.net/AgnesCallamard/rss"},
    {"name": "وال استریت ژورنال (WSJ)", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml"},
    {"name": "صدای آمریکا (VOA)", "url": "https://nitter.net/VOAIran/rss"},
    {"name": "رادیو فردا", "url": "https://nitter.net/RadioFarda_/rss"},
    {"name": "من و تو (Manoto)", "url": "https://nitter.net/manototv/rss"},
    {"name": "رویترز (Reuters Iran)", "url": "https://nitter.net/ReutersIran/rss"},
    {"name": "دویچه وله (DW) فارسی", "url": "https://nitter.net/dw_persian/rss"},
    # {"name": "خبرگزاری فارس", "url": "https://nitter.net/FarsNews_Agency/rss"},
    # {"name": "خبرگزاری تسنیم", "url": "https://nitter.net/Tasnimnews_Fa/rss"},
    # {"name": "خبرگزاری ایسنا", "url": "https://nitter.net/isna_farsi/rss"},
    {"name": "العربیه فارسی", "url": "https://nitter.net/AlArabiya_Far/rss"},
    {"name": "کیهان لندن", "url": "https://nitter.net/KayhanLondon/rss"},
    {"name": "وال استریت ژورنال", "url": "https://nitter.net/WSJ/rss"},
    
    # --- منابع اسرائیلی (نسخه توییتر برای پایداری ۱۰۰٪) ---
    {"name": "کانال ۱۱ اسرائیل (Kaan)", "url": "https://nitter.net/kann_news/rss"},
    {"name": "کانال ۱۲ اسرائیل (N12)", "url": "https://nitter.net/N12News/rss"},
    {"name": "کانال ۱۴ اسرائیل", "url": "https://nitter.net/Now14Israel/rss"},
    {"name": "تایمز اسرائیل (فارسی)", "url": "https://nitter.net/TimesofIsraelFA/rss"},
    {"name": "رادیو پیام اسرائیل", "url": "https://nitter.net/Be_Yisrael/rss"},
    {"name": "تحلیل استراتژیک ویدکاف", "url": "https://nitter.cz/vidcaff/rss"},
    {"name": "i24News English", "url": "https://nitter.net/i24NEWS_EN/rss"},
    {"name": "Jerusalem Post", "url": "https://nitter.net/Jerusalem_Post/rss"},
    {"name": "Times of Israel", "url": "https://nitter.net/TimesofIsrael/rss"},
    {"name": "Ynet News", "url": "https://nitter.net/ynetnews/rss"},
    {"name": "Israel Hayom", "url": "https://nitter.net/IsraelHayomEng/rss"}
]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS news 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  title_fa TEXT, title_en TEXT, 
                  desc_fa TEXT, desc_en TEXT, 
                  source TEXT, link TEXT UNIQUE, pub_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    conn.commit()
    conn.close()

def send_telegram(title_fa, description_fa, source, news_id):
    if not TOKEN or TOKEN == "YOUR_BOT_TOKEN": return
    
    # ۱. ساخت لینک اختصاصی خبر در سایت خودت
    # کاربر با کلیک روی این لینک، به سایت تو می‌آید تا متن کامل را بخواند
    my_site_link = f"https://irananalysis.onrender.com/news/{news_id}"
    
    # ۲. بریدن متن برای ساخت خلاصه (مثلاً ۱۸۰ کاراکتر اول)
    summary = description_fa[:180] + "..." if len(description_fa) > 180 else description_fa
    
    # ۳. چیدمان پیام تلگرام
    text = (f"🚀 <b>{title_fa}</b>\n\n"
            f"📝 {summary}\n\n"
            f"📍 منبع: {source}\n"
            f"————————————————\n"
            f"👇 <b>مشروح کامل خبر را در سایت بخوانید:</b>\n"
            f"🔗 {my_site_link}\n\n"
            f"🆔 @KhabarAnalysBan")
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=15)
    except: pass

# --- بخش آپدیت لوجیک (جایی که ترجمه اتفاق می‌افتد) ---
# در انتهای حلقه for در تابع update_logic این اصلاح را بزن:

                # ترجمه کامل (هم تیتر هم شرح)
                title_fa = translate_now(title_en)
                desc_fa = translate_now(desc_en)
                
                # ذخیره در دیتابیس
                c.execute("""INSERT INTO news (title_fa, title_en, desc_fa, desc_en, source, link, pub_date) 
                             VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                          (title_fa, title_en, desc_fa, desc_en, src['name'], link, sortable_date))
                conn.commit()
                
                # گرفتن ID خبری که همین الان ذخیره شد برای ساخت لینک سایت
                new_id = c.lastrowid
                
                # حالا ارسال به تلگرام با خلاصه و لینک سایت خودت
                send_telegram(title_fa, desc_fa, src['name'], new_id)
def translate_now(text):
    if not text or len(text) < 5: return text
    try:
        # این کتابخانه از نسخه‌های بهینه‌تر گوگل استفاده می‌کند
        translated = GoogleTranslator(source='auto', target='fa').translate(text)
        return translated
    except:
        return text

def update_logic():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # چک کردن زمان آخرین آپدیت (هر 5 دقیقه)
    c.execute("SELECT value FROM settings WHERE key='last_update'")
    row = c.fetchone()
    if row and (time.time() - float(row[0]) < 300):
        conn.close()
        return

    headers = {'User-Agent': 'Mozilla/5.0'}
    current_timestamp = time.time()
    
    for src in SOURCES:
        try:
            res = requests.get(src['url'], headers=headers, timeout=30)
            soup = BeautifulSoup(res.content, "xml")
            for item in soup.find_all('item')[:5]:
                link = item.link.text
                
                # مدیریت تاریخ و فیلتر 12 ساعت
                raw_date = item.pubDate.text if item.pubDate else ""
                try:
                    dt = parsedate_to_datetime(raw_date)
                    # فیلتر: اگر زمان انتشار بیش از 12 ساعت (43200 ثانیه) قبل بود، رد کن
                    if (current_timestamp - dt.timestamp()) > 43200:
                        continue
                        
                    sortable_date = dt.strftime('%Y-%m-%d %H:%M:%S')
                    display_date = dt.strftime('%H:%M - %Y/%m/%d')
                except:
                    # اگر تاریخ خوانده نشد، برای احتیاط از زمان حال استفاده می‌کنیم
                    sortable_date = time.strftime('%Y-%m-%d %H:%M:%S')
                    display_date = "نامشخص"

                c.execute("SELECT id FROM news WHERE link=?", (link,))
                if not c.fetchone():
                    title_en = item.title.text
                    desc_raw = item.description.text if item.description else ""
                    desc_en = BeautifulSoup(desc_raw, "html.parser").get_text()[:500]
                    
                    title_fa = translate_now(title_en)
                    desc_fa = translate_now(desc_en)
                    
                    c.execute("""INSERT INTO news (title_fa, title_en, desc_fa, desc_en, source, link, pub_date) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?)""", 
                              (title_fa, title_en, desc_fa, desc_en, src['name'], link, sortable_date))
                    conn.commit()
                    # این خط را در انتهای تابع update_logic پیدا و جایگزین کن:
                    send_telegram(f"{title_fa}\n{title_en}", desc_fa, src['name'], display_date, link)
        except: continue
    
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('last_update', ?)", (str(time.time()),))
    conn.commit()
    conn.close()

# اجرای اولیه دیتابیس
init_db()

@app.route('/')
def index():
    update_logic()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # مرتب‌سازی نزولی (DESC) برای قرارگیری جدیدترین‌ها در بالای لیست سایت
    c.execute("SELECT title_fa, title_en, desc_fa, desc_en, source, pub_date FROM news ORDER BY pub_date DESC LIMIT 50")
    news_data = []
    for r in c.fetchall():
        news_data.append({
            "title_fa": r[0], "title_en": r[1],
            "desc_fa": r[2], "desc_en": r[3],
            "source": r[4], "date": r[5]
        })
    conn.close()
    return render_template('index.html', news=news_data)
@app.route('/news/<int:news_id>')
def show_news(news_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # پیدا کردن خبر بر اساس ID که در لینک تلگرام فرستادیم
    c.execute("SELECT title_fa, desc_fa, source, pub_date FROM news WHERE id=?", (news_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        item = {"title": row[0], "content": row[1], "source": row[2], "date": row[3]}
        return render_template('post.html', item=item)
    return "خبر پیدا نشد!", 404
@app.route('/news/<int:news_id>')
def show_news(news_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # کشیدن اطلاعات خبر خاص از دیتابیس
    c.execute("SELECT title_fa, desc_fa, source, pub_date, link FROM news WHERE id=?", (news_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        # آماده‌سازی داده‌ها برای فرستادن به post.html
        news_item = {
            "title": row[0],
            "content": row[1],
            "source": row[2],
            "date": row[3],
            "original_link": row[4]
        }
        return render_template('post.html', item=news_item)
    return "<h1>متاسفانه خبر مورد نظر پیدا نشد!</h1>", 404
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
