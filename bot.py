import yfinance as yf
import requests
from datetime import datetime, time as dt_time
from time import sleep
import re

# -------------------- CONFIG --------------------
# Replace with your actual chat_id (from Telegram)
USERS = [
    {
        "chat_id": **************,   # 👈 put your Telegram chat_id here
        "portfolio": ["RELIANCE.NS", "TCS.NS", "INFY.NS"]  # 👈 put your tickers here
    },
]

NEWSDATA_API_KEY = "*************************************"
TELEGRAM_TOKEN = "***************************************"

MARKET_START = dt_time(9, 15)   # NSE market start
MARKET_END = dt_time(15, 30)    # NSE market end
# -------------------------------------------------

# Track last news per ticker to avoid duplicates
last_news_titles = {}

# -------------------- HELPERS --------------------
def escape_markdown(text):
    """Escape Markdown special characters for Telegram"""
    escape_chars = r"_*[]()~`>#+-=|{}.!\""
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", str(text))

def fetch_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d", interval="1h")
        if not hist.empty:
            return round(hist['Close'].iloc[-1], 2)
    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")
    return None

def fetch_news(ticker):
    url = f"https://newsdata.io/api/1/news?apikey={NEWSDATA_API_KEY}&q={ticker}&country=in&language=en"
    try:
        data = requests.get(url).json()
    except Exception as e:
        print(f"Error fetching news for {ticker}: {e}")
        return []

    news_list = []
    for article in data.get('results', []):
        title = article.get('title')
        link = article.get('link')
        if title and title not in last_news_titles.get(ticker, []):
            news_list.append({"ticker": ticker, "title": title, "url": link})
            last_news_titles.setdefault(ticker, []).append(title)
    return news_list

def build_telegram_message(news_data, prices):
    msg = "📊 *Portfolio Update*\n\n"
    for n in news_data:
        price = prices.get(n['ticker'], "N/A")
        msg += f"*{escape_markdown(n['ticker'])}* - ₹{price}\n"
        msg += f"{escape_markdown(n['title'])}\n{escape_markdown(n['url'])}\n\n"
    return msg.strip()

def send_telegram_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "MarkdownV2"}
    try:
        r = requests.post(url, data=payload)
        print("Telegram response:", r.json())  # Debugging
    except Exception as e:
        print(f"Error sending message to {chat_id}: {e}")

# -------------------- MAIN LOOP --------------------
def main_loop():
    # Send startup test message
    for user in USERS:
        send_telegram_message(user['chat_id'], "✅ Bot is running! You’ll start receiving updates.")

    while True:
        now = datetime.now().time()

        # Uncomment if you want only during market hours
        # if MARKET_START <= now <= MARKET_END:
        for user in USERS:
            chat_id = user['chat_id']
            portfolio = user['portfolio']
            prices = {t: fetch_price(t) for t in portfolio}

            all_news = []
            for t in portfolio:
                all_news.extend(fetch_news(t))

            if all_news:
                msg = build_telegram_message(all_news, prices)
                send_telegram_message(chat_id, msg)
                print(f"Update sent to {chat_id}")

        sleep(3600)  # check every hour

# -------------------- RUN --------------------
if __name__ == "__main__":
    main_loop()
