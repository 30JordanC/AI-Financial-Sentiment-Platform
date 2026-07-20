import json
import requests
from collections import defaultdict

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama2:latest"

# Load Reddit data
with open("/Users/jordan/Desktop/stock code/polygonapitesting/src/app/reddit_stock_data.json") as f:
    data = json.load(f)

# Group posts by ticker
posts_by_ticker = defaultdict(list)
for post in data:
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
        f"Summarize what the Reddit community is saying about {ticker} based on these posts and comments. "
        "Then, give a sentiment rating out of 5 (1=very negative, 5=very positive) with a short explanation. "
        "Here is the data:\n"
        f"{combined_text[:4000]}"  # Limit to 4000 chars to avoid overloading the model
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
