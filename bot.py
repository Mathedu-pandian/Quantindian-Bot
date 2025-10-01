import yfinance as yf
import requests
import pandas as pd
from datetime import datetime, time as dt_time
from time import sleep
from nltk.sentiment import SentimentIntensityAnalyzer
from transformers import pipeline
from flask import Flask
from threading import Thread
import os

# -------------------- ENVIRONMENT VARIABLES --------------------
USERS_CSV = os.getenv("USERS_CSV", "users.csv")
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
MARKET_START = dt_time(9, 15)  # NSE market start
MARKET_END = dt_time(15, 30)   # NSE market end
REPORT_HOUR = 16                # End-of-day summary
# ---------------------------------------------------------------

# Initialize NLP tools
summarizer = pipeline("summarization")
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
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1d", interval="1h")
    if not hist.empty:
        return hist['Close'].iloc[-1]
    return None

def fetch_news(ticker):
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://newsdata.io/api/1/news?apikey={NEWSDATA_API_KEY}&q={ticker}&country=in&language=en"
    data = requests.get(url).json()
    news_list = []
    for n in data.get("results", [])[:3]:
        title = n.get('title', '')
        if title not in last_news_titles.get(ticker, []):
            news_list.append({
                "title": title,
                "url": n.get('link', ''),
                "ticker": ticker,
                "time": datetime.now().strftime("%H:%M")
            })
            last_news_titles.setdefault(ticker, []).append(title)
    return news_list

def save_data(prices, news_data):
    hour = datetime.now().strftime("%H:%M")
    df_prices = pd.DataFrame([prices], index=[hour])
    df_prices.to_csv("portfolio_prices.csv", mode='a', header=False)
    if news_data:
        df_news = pd.DataFrame(news_data)
        df_news.to_csv("portfolio_news.csv", mode='a', header=False)

def generate_summary(user_portfolio):
    df = pd.read_csv("portfolio_news.csv", names=["title","url","ticker","time"])
    summary_results = []
    for t in user_portfolio:
        news_texts = df[df['ticker']==t]['title'].tolist()
        combined_text = " ".join(news_texts)
        if combined_text:
            summary = summarizer(combined_text, max_length=50, min_length=10, do_sample=False)[0]['summary_text']
            sentiment_score = sia.polarity_scores(combined_text)['compound']
            sentiment_label = "Bullish" if sentiment_score>0.05 else "Bearish" if sentiment_score<-0.05 else "Neutral"
            summary_results.append({
                "ticker": t,
                "summary": summary,
                "sentiment": sentiment_label
            })
    return summary_results

def build_telegram_message(summary_results, prices):
    msg = "📊 *Portfolio Update*\n\n"
    for r in summary_results:
        price = prices.get(r['ticker'], "N/A")
        msg += f"*{r['ticker']}* | Price: {price} | Sentiment: {r['sentiment']}\n"
        msg += f"{r['summary']}\n\n"
    return msg

def send_telegram_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    requests.post(url, data=payload)

# -------------------- MAIN LOOP --------------------
while True:
    now = datetime.now().time()
    users_df = pd.read_csv(USERS_CSV)

    # Hourly alerts during market hours
    if MARKET_START <= now <= MARKET_END:
        for _, row in users_df.iterrows():
            chat_id = row['chat_id']
            portfolio = row['portfolio'].split(",")
            prices = {t: fetch_price(t) for t in portfolio}
            all_news = []
            for t in portfolio:
                all_news.extend(fetch_news(t))
            save_data(prices, all_news)
            # Only send if there is new news
            if all_news:
                summary_results = generate_summary(portfolio)
                msg = build_telegram_message(summary_results, prices)
                send_telegram_message(chat_id, msg)
                print(f"Hourly update sent to {chat_id}")
    
    # End-of-day summary after market close
    if now.hour == REPORT_HOUR:
        for _, row in users_df.iterrows():
            chat_id = row['chat_id']
            portfolio = row['portfolio'].split(",")
            prices = {t: fetch_price(t) for t in portfolio}
            summary_results = generate_summary(portfolio)
            msg = build_telegram_message(summary_results, prices)
            send_telegram_message(chat_id, msg)
            print(f"End-of-day report sent to {chat_id}")
        sleep(3600)  # avoid duplicate sending within same hour

    sleep(3600)  # hourly loop
