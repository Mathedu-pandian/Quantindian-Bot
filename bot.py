import yfinance as yf
import requests
import pandas as pd
from datetime import datetime, time as dt_time
from time import sleep
from nltk.sentiment import SentimentIntensityAnalyzer
from flask import Flask
from threading import Thread
import os

# -------------------- ENVIRONMENT VARIABLES --------------------
USERS_CSV = os.getenv("USERS_CSV", "users.csv")
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MARKET_START = dt_time(9, 15)   # NSE market start
MARKET_END = dt_time(15, 30)    # NSE market end
REPORT_HOUR = 16                # End-of-day summary
# ---------------------------------------------------------------

# Initialize Sentiment Analyzer
sia = SentimentIntensityAnalyzer()

# Track last news per ticker to avoid duplicates
last_news_titles = {}

# -------------------- FLASK KEEP-ALIVE --------------------
app = Flask("")

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run_flask).start()

# -------------------- HELPER FUNCTIONS --------------------
def fetch_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d", interval="1h")
        if not hist.empty:
            return round(hist['Close'].iloc[-1], 2)
    except Exception as e:
        print(f"Price fetch error for {ticker}: {e}")
    return None

def fetch_news(ticker):
    url = f"https://newsdata.io/api/1/news?apikey={NEWSDATA_API_KEY}&q={ticker}&country=in&language=en"
    data = requests.get(url).json()
    news_list = []
    for n in data.get("results", [])[:3]:
        title = n.get('title', '')
        if title not in last_news_titles.get(ticker, []):
            sentiment_score = sia.polarity_scores(title)['compound']
            sentiment_label = "Bullish" if sentiment_score > 0.05 else "Bearish" if sentiment_score < -0.05 else "Neutral"
            news_list.append({
                "title": title,
                "url": n.get('link', ''),
                "ticker": ticker,
                "sentiment": sentiment_label,
                "time": datetime.now().strftime("%H:%M")
            })
            last_news_titles.setdefault(ticker, []).append(title)
    return news_list

def build_telegram_message(chat_id, portfolio, news_data, prices):
    msg = f"📊 *Portfolio Update for {chat_id}*\n\n"

    for ticker in portfolio:
        price = prices.get(ticker, "N/A")
        msg += f"*{ticker}* | Price: {price}\n"

        ticker_news = [n for n in news_data if n['ticker'] == ticker]
        if ticker_news:
            for n in ticker_news:
                msg += f"- {n['sentiment']}: {n['title']}\n{n['url']}\n"
        else:
            msg += "- No fresh news found\n"

        msg += "\n"

    return msg

def send_telegram_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Telegram send error for {chat_id}: {e}")

# -------------------- MAIN LOOP --------------------
while True:
    now = datetime.now().time()
    users_df = pd.read_csv(USERS_CSV)

    for _, row in users_df.iterrows():
        chat_id = row['users']
        portfolio = [
            str(row[col]).strip()
            for col in users_df.columns
            if col.startswith("Portfolio") and pd.notna(row[col])
        ]

        prices = {t: fetch_price(t) for t in portfolio}

        # Regular updates during market hours
        if MARKET_START <= now <= MARKET_END:
            all_news = []
            for t in portfolio:
                all_news.extend(fetch_news(t))

            if all_news:
                msg = build_telegram_message(chat_id, portfolio, all_news, prices)
                send_telegram_message(chat_id, msg)
                print(f"Update sent to {chat_id}")

        # End-of-day summary at REPORT_HOUR
        if now.hour == REPORT_HOUR and now.minute < 5:  # send once within first 5 mins
            summary = "📌 *End of Day Portfolio Summary*\n\n"
            for t in portfolio:
                price = prices.get(t, "N/A")
                summary += f"*{t}* | Closing Price: {price}\n"
            send_telegram_message(chat_id, summary)
            print(f"End-of-day summary sent to {chat_id}")

    sleep(300)  # check every 5 mins
