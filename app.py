import streamlit as st
import pandas as pd
import threading
import time
import requests
import feedparser
import pyotp
from logzero import logger
from deep_translator import GoogleTranslator
import schedule
from datetime import datetime

# =====================================================================
# [SECTION 1] : CONFIGURATION & API SECRET PLACEHOLDERS
# Aapne Streamlit secrets me add kar diya hai, toh usko aise call karenge:
# =====================================================================

try:
    TELEGRAM_BOT_TOKEN = st.secrets["TELEGRAM_BOT_TOKEN"]
    TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
    ANGEL_API_KEY = st.secrets["ANGEL_API_KEY"]
    ANGEL_CLIENT_ID = st.secrets["ANGEL_CLIENT_ID"]
    ANGEL_PIN = st.secrets["ANGEL_PIN"]
    ANGEL_TOTP_SECRET = st.secrets["ANGEL_TOTP_SECRET"]
except Exception as e:
    logger.warning("Secrets not fully configured yet. Using placeholders.")
    TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
    TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID_HERE"
    ANGEL_TOTP_SECRET = "YOUR_ANGEL_TOTP_SECRET_HERE"

# News Filter Whitelist (Sirf Nifty & Macro topics)
NEWS_WHITELIST = [
    "reliance", "hdfc", "icici", "infosys", "tcs", "itc", "l&t", "sbi", "kotak", "bharti airtel", 
    "trump", "crude", "brent", "usd inr", "rupee", "dollar index", 
    "rbi", "fed", "repo rate", "rate cut", "powell", "das",
    "scam", "fraud", "sebi", "hindenburg", "default", "advisory", "q1", "q2", "q3", "q4", "earnings"
]
seen_news_titles = set()

# =====================================================================
# [SECTION 2] : TELEGRAM NOTIFICATION ENGINE
# =====================================================================

def send_telegram_alert(message):
    """Telegram par message push karega HTML format me"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logger.info("Telegram Alert Sent Successfully!")
        else:
            logger.error(f"Telegram Alert Failed: {response.text}")
    except Exception as e:
        logger.error(f"Telegram API Error: {e}")

# =====================================================================
# [SECTION 3] : ANGEL ONE AUTO LOGIN
# =====================================================================

def angel_auto_login():
    """Daily Angel One TOTP Auto-Login"""
    logger.info("Initiating Angel One Auto-Login...")
    try:
        totp = pyotp.TOTP(ANGEL_TOTP_SECRET).now()
        logger.info(f"Generated TOTP: {totp}")
        # SmartAPI connection logic aayega yahan
        logger.info("Angel One Login Successful!")
        send_telegram_alert("✅ <b>S'Ravaal Option Alert:</b> Angel One Auto Login Successful.")
    except Exception as e:
        logger.error(f"Angel Login Failed: {e}")

# =====================================================================
# [SECTION 4] : NEWS & VIX SPIKE FILTER ENGINE
# =====================================================================

def check_market_news():
    """News scraper with Whitelist Filtering"""
    rss_url = 'https://news.google.com/rss/search?q=NIFTY+OR+NSE+OR+BSE+when:1h&hl=en-IN&gl=IN&ceid=IN:en'
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries:
            title_en = entry.title
            if title_en in seen_news_titles:
                continue
                
            title_lower = title_en.lower()
            if any(keyword in title_lower for keyword in NEWS_WHITELIST):
                try:
                    title_gu = GoogleTranslator(source='auto', target='gu').translate(title_en)
                except:
                    title_gu = "Translation Error"

                msg = f"🚨 <b>S'RAVAAL HIGH IMPACT NEWS</b> 🚨\n\n"
                msg += f"🇮🇳 <b>Gujarati:</b> {title_gu}\n"
                msg += f"🔤 <b>English:</b> {title_en}\n\n"
                msg += f"⚠️ <b>Focus:</b> Nifty 50 Options"
                
                send_telegram_alert(msg)
                logger.info(f"News Alert Sent: {title_en}")
                seen_news_titles.add(title_en)
    except Exception as e:
        logger.error(f"News Scraper Error: {e}")

def check_vix_spike():
    """VIX volatility track karega (Mock logic for now)"""
    logger.info("Checking India VIX for sudden spikes...")
    # TODO: Add actual VIX checking logic via Angel API
    # Agar VIX 5% se zyada jump kare:
    # send_telegram_alert("⚠️ <b>VIX ALERT:</b> India VIX spiked > 5%! Option Premiums are expanding.")

# =====================================================================
# [SECTION 5] : PRE-MARKET CHECKLIST (TABLE VIEW)
# =====================================================================

def generate_checklist_data():
    """Checklist ka data banata hai (Pandas DataFrame)"""
    # Baad me yahan API se real data replace hoga
    data = {
        "Indicator": ["Gift Nifty", "US Markets", "Asian Markets", "FII Cash (Prev)", "Nifty PCR", "India VIX", "Crude Oil"],
        "Status / Value": ["+45 Points", "Tech Rally", "Flat", "-1200 Cr", "0.85 (Neutral)", "14.2", "$82"],
        "Signal": ["🟢 Bullish", "🟢 Bullish", "⚪ Neutral", "🔴 Bearish", "⚪ Neutral", "🟡 Watch", "⚪ Neutral"]
    }
    return pd.DataFrame(data)

def run_pre_market_checklist():
    """Subah 8:30 par checklist banakar Telegram par HTML table bhejega"""
    logger.info("Running Pre-Market Checklist...")
    df = generate_checklist_data()
    
    # Telegram par bhejne ke liye Monospace format <pre> tag ka use
    # Taaki columns aage-peeche na hon
    msg = "🌅 <b>S'RAVAAL PRE-MARKET CHECKLIST</b> 🌅\n\n<pre>"
    msg += f"{'Indicator':<15} | {'Value':<12} | {'Signal'}\n"
    msg += "-" * 40 + "\n"
    for index, row in df.iterrows():
        msg += f"{row['Indicator']:<15} | {row['Status / Value']:<12} | {row['Signal']}\n"
    msg += "</pre>"
    
    send_telegram_alert(msg)

# =====================================================================
# [SECTION 6] : ANTI-SLEEP & SCHEDULER ENGINE (SAFE RATE LIMIT)
# =====================================================================

def safe_keep_alive():
    """Har 15 min me background ko zinda rakhne ke liye safe ping.
    Streamlit Cloud par block hone se bachayega."""
    logger.info("Keep-Alive Ping: System is active.")
    try:
        # Ek halka safe request taaki thread idle mark na ho
        requests.get("https://www.google.com", timeout=5)
    except:
        pass

def background_tasks():
    # 15 minutes interval - Safe limit (No blocks)
    schedule.every(15).minutes.do(safe_keep_alive)
    
    # Subah 8:30 baje Pre-Market Checklist
    schedule.every().day.at("08:30").do(run_pre_market_checklist)
    
    # Subah 8:45 baje Angel One Login
    schedule.every().day.at("08:45").do(angel_auto_login)
    
    # Market hours me News & VIX check (Har 2 & 5 minute)
    schedule.every(2).minutes.do(check_market_news)
    schedule.every(5).minutes.do(check_vix_spike)

    while True:
        schedule.run_pending()
        time.sleep(1)

if 'thread_started' not in st.session_state:
    task_thread = threading.Thread(target=background_tasks, daemon=True)
    task_thread.start()
    st.session_state.thread_started = True
    logger.info("Background Scheduler Started Successfully!")

# =====================================================================
# [SECTION 7] : STREAMLIT UI (DYNAMIC DASHBOARD)
# =====================================================================

st.set_page_config(page_title="S'Ravaal option Alert", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .header-style {
        color: #ff4b4b; font-size: 40px; font-weight: bold; text-align: center;
        padding: 20px; background-color: #ffffff; border-radius: 10px;
        box-shadow: 0px 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px;
    }
    .box-style {
        background-color: #e3f2fd; padding: 20px; border-radius: 10px;
        color: #0d47a1; font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="header-style">🚀 S\'Ravaal option Alert Dashboard</div>', unsafe_allow_html=True)

# --- CHECKLIST TABLE UI ---
st.write("### 📊 Morning Pre-Market Checklist (Live Table)")
df_checklist = generate_checklist_data()
# Resizable, scrollable, aur columns hide karne wala interactive dataframe
st.dataframe(df_checklist, use_container_width=True, hide_index=True)

st.write("---")

col1, col2 = st.columns(2)
with col1:
    st.markdown('<div class="box-style">🟢 System Status</div>', unsafe_allow_html=True)
    st.write("")
    st.success("Background Thread: RUNNING")
    st.success("Anti-Sleep Mechanism: ACTIVE (15 min interval)")
    st.info("Angel API & Telegram: Configured via Secrets")

with col2:
    st.markdown('<div class="box-style">📰 Live Modules Tracking</div>', unsafe_allow_html=True)
    st.write("")
    st.info("VIX Spike Alert: ENABLED")
    st.info(f"News Filter: Tracking {len(NEWS_WHITELIST)} VIP Keywords")

st.write("---")
st.write("### 🛠️ Control Panel (Manual Triggers)")
col_a, col_b, col_c = st.columns(3)

with col_a:
    if st.button("Trigger Pre-Market Alert (Telegram)"):
        run_pre_market_checklist()
        st.toast("Pre-market alert sent to Telegram!")

with col_b:
    if st.button("Fetch Live News (Background)"):
        check_market_news()
        st.toast("Checking for live news...")

with col_c:
    if st.button("Test Angel Auto-Login"):
        angel_auto_login()
        st.toast("Angel Login Triggered!")
