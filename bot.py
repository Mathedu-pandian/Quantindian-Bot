# bot.py - QuantIndian Bot (without sentiment analysis)

import os
import requests
import yfinance as yf
import pandas as pd
from flask import Flask, request
from bs4 import BeautifulSoup
import telegram

# ----------------- CONFIG -----------------
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"  # Replace with your Telegram chat ID

bot = telegram.Bot(token=TELEGRAM_TOKEN)
app = Flask(__name__)

# ----------------- STOCK FUNCTION -----------------
def get_stock_price(ticker):
    """Fetch latest stock price using yfinance"""
    stock = yf.Ticker(ticker)
    data = stock.history(period="1d")
    if not data.empty:
        return data['Close'].iloc[-1]
    return None

# ----------------- NEWS FUNCTION -----------------
def get_latest_news(url):
    """Scrape news headlines from a webpage"""
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.content, "html.parser")
        headlines = [h.text.strip() for h in soup.find_all("h2")][:5]  # Top 5 headlines
        return headlines
    except Exception as e:
        return [f"Error fetching news: {e}"]

# ----------------- TELEGRAM FUNCTION -----------------
def send_telegram_message(message):
    """Send message to Telegram"""
    bot.send_message(chat_id=CHAT_ID, text=message)

# ----------------- FLASK ROUTES -----------------
@app.route('/')
def home():
    return "QuantIndian Bot is running!"

@app.route('/stock/<ticker>')
def stock(ticker):
    price = get_stock_price(ticker)
    if price:
        return f"The latest price of {ticker} is {price}"
    else:
        return f"Could not fetch price for {ticker}"

@app.route('/news')
def news():
    url = "https://www.moneycontrol.com/news/"  # Example news site
    headlines = get_latest_news(url)
    return "<br>".join(headlines)

@app.route('/send_message/<message>')
def telegram_message(message):
    send_telegram_message(message)
    return f"Message sent: {message}"

# ----------------- RUN APP -----------------
if __name__ == "__main__":
    app.run(debug=True)
