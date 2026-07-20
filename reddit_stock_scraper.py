import praw
import yfinance as yf
import time
import json
import pandas as pd
import requests
from collections import defaultdict
from supabase import create_client, Client
import re

# Reddit API credentials (replace with your own)
REDDIT_CLIENT_ID = 
REDDIT_CLIENT_SECRET = 
REDDIT_USER_AGENT = 'stock-scraper-script by /u/Sensitive-Pass-640'

# Initialize Reddit API
reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT
)

# Get S&P 500 tickers from Wikipedia
#table = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')
#sp500_df = table[0]
#tickers = sp500_df['Symbol'].tolist()
#tickers = tickers[:5] #limit to 5 tickers for testing, delete later for all 500

# Use your custom list instead:
tickers = ["NVDA", "META", "TSLA", "MSFT", "AMD", "AAPL", "PLTR", "CRWD", "SHOP", "SPOT", "RIVN", "ZM", "SQ"]

# Subreddits to search
subreddits = ['stocks', 'investing', 'wallstreetbets']

results = []

for ticker in tickers:
    print(f"Searching for posts about: {ticker}")
    for subreddit in subreddits:
        try:
            for submission in reddit.subreddit(subreddit).search(ticker, limit=5):
                post_data = {
                    "ticker": ticker,
                    "subreddit": subreddit,
                    "title": submission.title,
                    "selftext": submission.selftext,
                    "author": str(submission.author),
                    "score": submission.score,
                    "num_comments": submission.num_comments,
                    "created_utc": submission.created_utc,
                    "url": submission.url,
                    "comments": []
                }
                submission.comments.replace_more(limit=0)
                for comment in submission.comments.list():
                    post_data["comments"].append({
                        "author": str(comment.author),
                        "body": comment.body,
                        "score": comment.score,
                        "created_utc": comment.created_utc
                    })
                results.append(post_data)
        except Exception as e:
            print(f"Error searching {subreddit} for {ticker}: {e}")
    time.sleep(1)

with open("reddit_stock_data.json", "w") as f:
    json.dump(results, f, indent=2)

print("Done scraping Reddit for stock tickers. Data saved to reddit_stock_data.json.")

# --- Summarize with Ollama ---
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama2:latest"

# Group posts by ticker
posts_by_ticker = defaultdict(list)
for post in results: # Use 'results' directly as it's already scraped
    ticker = post.get("ticker")
    if ticker:
        # Combine title, selftext, and top comments
        text = post.get("title", "") + "\n" + post.get("selftext", "")
        for comment in post.get("comments", []):
            text += "\nComment: " + comment.get("body", "")
        posts_by_ticker[ticker].append(text)

# For each ticker, summarize and rate
for ticker, posts in posts_by_ticker.items():
    combined_text = "\n\n".join(posts)
    prompt = (
        f"Summarize what the Reddit community is saying about {ticker} based on these posts and comments. Then, on a new line, write: 'Rating: X/5' (where X is a number from 1 to 5, 1=very negative, 5=very positive)."
    )
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }
    )
    result = response.json().get("response", "")
    print(f"\n=== {ticker} ===\n{result}\n{'='*40}")

    # Extract rating
    # Try to match "X/5" first
    match = re.search(r'(\d(?:\.\d)?)\s*/\s*5', result)
    if not match:
        # Try to match "Sentiment rating: X" or "Rating: X"
        match = re.search(r'(?:Sentiment rating|Rating)[:\s]+(\d(?:\.\d)?)', result, re.IGNORECASE)
    rating = float(match.group(1)) if match else None

    SUPABASE_URL = 
    SUPABASE_KEY =   # <-- Replace with your anon key
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Update the community_rating for the ticker
    print(f"Updating {ticker} with rating {rating}")
    exists = supabase.table("MARKET_SENTIMENT").select("ticker").eq("ticker", ticker).execute()
    print(f"Ticker {ticker!r} exists in Supabase: {exists.data}")
    response = supabase.table("MARKET_SENTIMENT").update({"community_rating": rating}).eq("ticker", ticker).execute()
    print(f"Supabase response: {response}")

    if rating is None:
        print(f"WARNING: No rating found for {ticker}. Ollama output was:\n{result}")

print("Tickers being processed:", tickers) 
