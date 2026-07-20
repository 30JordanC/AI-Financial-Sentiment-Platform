import json
from typing import List, Dict
import praw
import snscrape.modules.twitter as sntwitter
import requests
import ollama  # or your preferred LLM client
from supabase import create_client, Client
import sys
from config import USER_EMAIL, USER_PASSWORD

# TODO: Add your API keys/configs here
REDDIT_CONFIG = {
    'client_id': 'ahJABGw7aPjP2SSTGJWzgQ',
    'client_secret': 'ymNMtIwMOavK4yxZKvFEuREjX0R4TA',
    'user_agent': 'stock-scraper-script by /u/Sensitive-Pass-640',
}
TWITTER_CONFIG = {
    # 'bearer_token': '',
}
STOCKTWITS_CONFIG = {
    # No API key required for public endpoints
}

# Example list of stock tickers (replace with S&P 500 or your own list)
TICKERS = ["NVDA", "META", "TSLA", "MSFT", "AMD", "AAPL", "PLTR", "CRWD", "SHOP", "SPOT", "RIVN", "ZM", "SQ"]

TICKER_TO_COMPANY = {
    "NVDA": "NVIDIA",
    "META": "Meta Platforms",
    "TSLA": "Tesla",
    "MSFT": "Microsoft",
    "AMD": "Advanced Micro Devices",
    "AAPL": "Apple",
    "PLTR": "Palantir Technologies",
    "CRWD": "CrowdStrike",
    "SHOP": "Shopify",
    "SPOT": "Spotify",
    "RIVN": "Rivian",
    "ZM": "Zoom Video Communications",
    "SQ": "Block",
    # Add more as needed
}

SUPABASE_URL = "https://cdzkowllflvoptyuvrrm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNkemtvd2xsZmx2b3B0eXV2cnJtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkxNzgzODMsImV4cCI6MjA2NDc1NDM4M30.Boe4aglV3FmFT660cWpjMopEJqHG6zTdSrmDFebukuc"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def authenticate_and_get_user_id():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": USER_EMAIL,
            "password": USER_PASSWORD
        })
        user_id = auth_response.user.id
        print(f"Successfully authenticated user: {user_id}")
        return supabase, user_id
    except Exception as e:
        print(f"Fatal Error: Could not authenticate with Supabase. {e}")
        sys.exit(1)


def scrape_reddit(ticker: str) -> List[Dict]:
    """Scrape Reddit for posts mentioning the ticker."""
    reddit = praw.Reddit(
        client_id=REDDIT_CONFIG['client_id'],
        client_secret=REDDIT_CONFIG['client_secret'],
        user_agent=REDDIT_CONFIG['user_agent']
    )
    results = []
    # Search in popular stock-related subreddits
    subreddits = ['stocks', 'investing', 'wallstreetbets', 'StockMarket', 'pennystocks']
    query = f'${ticker} OR {ticker}'
    for subreddit in subreddits:
        for submission in reddit.subreddit(subreddit).search(query, sort='new', limit=10):
            results.append({
                'title': submission.title,
                'subreddit': subreddit,
                'author': str(submission.author),
                'score': submission.score,
                'created_utc': submission.created_utc,
                'permalink': f"https://reddit.com{submission.permalink}",
            })
    return results


def scrape_twitter(ticker: str) -> List[Dict]:
    """Scrape Twitter/X for tweets mentioning the ticker using snscrape."""
    query = f'${ticker} OR {ticker}'
    results = []
    for i, tweet in enumerate(sntwitter.TwitterSearchScraper(query).get_items()):
        if i >= 10:
            break
        results.append({
            'text': tweet.content,
            'username': tweet.user.username,
            'created_at': tweet.date.isoformat(),
            'retweet_count': tweet.retweetCount,
            'like_count': tweet.likeCount,
            'tweet_id': tweet.id,
            'permalink': f'https://twitter.com/i/web/status/{tweet.id}',
        })
    return results


def scrape_stocktwits(ticker: str) -> List[Dict]:
    """Scrape StockTwits for messages mentioning the ticker using their public API."""
    url = f'https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json'
    results = []
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            for msg in data.get('messages', [])[:10]:
                results.append({
                    'body': msg.get('body'),
                    'username': msg.get('user', {}).get('username'),
                    'created_at': msg.get('created_at'),
                    'message_id': msg.get('id'),
                    'permalink': msg.get('links', [{}])[0].get('url') if msg.get('links') else None,
                })
    except Exception as e:
        print(f"[StockTwits] Error scraping {ticker}: {e}")
    return results


def aggregate_posts(reddit_posts, stocktwits_posts):
    # Add source field to each post
    for post in reddit_posts:
        post['source'] = 'reddit'
    for post in stocktwits_posts:
        post['source'] = 'stocktwits'
    return reddit_posts + stocktwits_posts


def find_top_post(posts, ticker, company_name=None):
    # Use AI to filter relevant posts
    relevant_posts = [p for p in posts if is_post_relevant_ai(p, ticker, company_name)]
    if not relevant_posts:
        return None
    def get_score(post):
        if post['source'] == 'reddit':
            return post.get('score', 0)
        elif post['source'] == 'stocktwits':
            from dateutil import parser
            try:
                return parser.parse(post.get('created_at', '1970-01-01')).timestamp()
            except Exception:
                return 0
        return 0
    return max(relevant_posts, key=get_score)


def get_hype_score_and_top_post(ticker, posts):
    # Sort posts by score/likes
    top_post = max(posts, key=lambda p: p.get('score', 0) or p.get('like_count', 0) or 0)
    # Build prompt
    prompt = f"Here are recent social media posts about {ticker}:\n"
    for i, post in enumerate(posts):
        # Try to get the main text content from 'text', 'body', or fallback to an empty string
        content = post.get('text') or post.get('body') or ''
        score = post.get('score') or post.get('like_count') or post.get('message_id') or 0
        prompt += f"{i+1}. {content} (score: {score})\n"
    prompt += (
        "\nPlease:\n"
        "- Give a hype score for {ticker} between 0 and 100 (where 0 is no hype and 100 is maximum hype) based on these posts.\n"
        "- Identify the single most positive or most liked post.\n"
        "Respond in this format:\n"
        "Hype Score: <number>\n"
        "Top Post: <text>\n"
    )
    # Call Ollama
    response = ollama.chat(model='llama2:latest', messages=[{'role': 'user', 'content': prompt}])
    content = response['message']['content']
    hype_score = None
    top_post_text = None

    # Try to extract the hype score and top post using more flexible parsing
    import re

    # Look for "Hype Score: <number>"
    hype_score_match = re.search(r'Hype Score\s*:\s*(\d+)', content, re.IGNORECASE)
    if hype_score_match:
        hype_score = int(hype_score_match.group(1))

    # Look for "Top Post: <text>" (may be multi-line)
    top_post_match = re.search(r'Top Post\s*:\s*(.*)', content, re.IGNORECASE | re.DOTALL)
    if top_post_match:
        # Get everything after "Top Post:" and strip leading/trailing whitespace
        top_post_text = top_post_match.group(1).strip()

    # After extracting hype_score
    if hype_score is not None:
        hype_score = max(0, min(100, hype_score))

    return hype_score, top_post_text


def is_post_relevant_ai(post, ticker, company_name=None):
    content = post.get('text') or post.get('body') or post.get('title') or ''
    if not content.strip():
        return False
    company_part = f" ({company_name})" if company_name else ""
    prompt = (
        f"Is the following post specifically about {ticker}{company_part}? "
        "Reply only YES or NO.\n\n"
        f"Post: {content}"
    )
    response = ollama.chat(model='llama2:latest', messages=[{'role': 'user', 'content': prompt}])
    answer = response['message']['content'].strip().lower()
    return answer.startswith('yes')


def update_hype_score_in_supabase(supabase, user_id, ticker, hype_score, top_post_content, top_post_link):
    supabase.table("hype_scores").upsert({
        "user_id": user_id,
        "ticker": ticker,
        "hype_score": hype_score,
        "top_post_context": top_post_content,
        "top_post_link": top_post_link
    }).execute()


def main():
    supabase, user_id = authenticate_and_get_user_id()
    all_data = {}
    for ticker in TICKERS:
        reddit_data = scrape_reddit(ticker)
        stocktwits_data = scrape_stocktwits(ticker)
        combined_posts = aggregate_posts(reddit_data, stocktwits_data)
        company_name = TICKER_TO_COMPANY.get(ticker, ticker)
        top_post = find_top_post(combined_posts, ticker, company_name=company_name)
        hype_score, ollama_top_post = (None, None)
        if combined_posts:
            hype_score, ollama_top_post = get_hype_score_and_top_post(ticker, combined_posts)

        if top_post:
            content = top_post.get('text') or top_post.get('body') or top_post.get('title') or ''
            permalink = top_post.get('permalink')
        else:
            content = None
            permalink = None

        all_data[ticker] = {
            'reddit': reddit_data,
            'stocktwits': stocktwits_data,
            'all_posts': combined_posts,
            'top_post': top_post,
            'hype_score': hype_score,
            'ollama_top_post': ollama_top_post,
        }
    # Save to JSON
    with open('hype_data.json', 'w') as f:
        json.dump(all_data, f, indent=2)
    print("Scraping and hype scoring complete. Data saved to hype_data.json.")

    # Display results in terminal
    print("\n=== Hype Tracker Results ===")
    for ticker, data in all_data.items():
        print(f"\nTicker: {ticker}")
        print(f"Hype Score: {data.get('hype_score', 'N/A')}")
        top_post = data.get('top_post')
        if top_post:
            content = top_post.get('text') or top_post.get('body') or top_post.get('title') or ''
            print(f"Top Post: {content}")
            permalink = top_post.get('permalink')
            if permalink:
                print(f"Link: {permalink}")
        else:
            content = None
            permalink = None
            print("Top Post: N/A")

    # Update Supabase after everything else
    for ticker, data in all_data.items():
        hype_score = data.get('hype_score')
        top_post = data.get('top_post')
        if top_post:
            content = top_post.get('text') or top_post.get('body') or top_post.get('title') or ''
            permalink = top_post.get('permalink')
        else:
            content = None
            permalink = None
        update_hype_score_in_supabase(
            supabase,
            user_id,
            ticker,
            hype_score,
            content,
            permalink
        )


if __name__ == "__main__":
    main() 