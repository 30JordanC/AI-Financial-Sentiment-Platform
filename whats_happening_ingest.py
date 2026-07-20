import requests
from bs4 import BeautifulSoup
import json
import feedparser
from supabase import create_client
import getpass
import sys
import os
# Import config values
from config import SUPABASE_URL, SUPABASE_KEY, OLLAMA_API_URL, TICKERS, USER_EMAIL, USER_PASSWORD

sys.path.append(os.path.dirname(__file__))

# --- Yahoo Finance Article Scraping ---
def scrape_yahoo_article(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    # Debug: print possible headline tags
    print("H1:", soup.find("h1"))
    print("TITLE:", soup.find("title"))
    print("OG:TITLE:", soup.find("meta", property="og:title"))
    print("TWITTER:TITLE:", soup.find("meta", attrs={"name": "twitter:title"}))
    # Headline extraction: prefer og:title, then twitter:title, then <title>, then <h1>
    headline = ""
    meta_headline = soup.find("meta", property="og:title")
    if meta_headline and meta_headline.get("content"):
        headline = meta_headline["content"].strip()
    else:
        twitter_headline = soup.find("meta", attrs={"name": "twitter:title"})
        if twitter_headline and twitter_headline.get("content"):
            headline = twitter_headline["content"].strip()
        else:
            title_tag = soup.find("title")
            if title_tag and title_tag.text.strip():
                headline = title_tag.text.strip()
            else:
                headline_tag = soup.find("h1")
                if headline_tag and headline_tag.text.strip():
                    headline = headline_tag.text.strip()
    if not headline:
        print("No headline found. Printing soup for debugging:")
        print(soup.prettify())
    # Article body (all paragraphs)
    body_div = soup.find("div", class_="caas-body")
    if body_div:
        paragraphs = [p.text.strip() for p in body_div.find_all("p")]
        summary = " ".join(paragraphs)
    else:
        # Fallback: get all <p> tags on the page
        paragraphs = [p.text.strip() for p in soup.find_all("p")]
        summary = " ".join(paragraphs)
    # Date extraction (already robust)
    date_tag = soup.find("time")
    date = date_tag.text.strip() if date_tag else ""
    return {
        "headline": headline,
        "summary": summary,
        "date": date,
        "url": url,
        "source": "Yahoo Finance"
    }

# Use TICKERS from config
# Paste your news article URLs here
URLS = [
    # NVDA
    "https://ca.news.yahoo.com/m/0a7ef164-4573-3a96-a04f-289c4072f559/nvidia-chip-stocks-have.html",
    "https://ca.news.yahoo.com/m/8faf8b57-cb78-3469-a64b-0f81f4e9dde7/nvidia-ai-data-center-stocks.html",
    "https://ca.finance.yahoo.com/news/nvidia-stock-closes-at-record-as-ai-chipmaker-nears-being-crowned-most-valuable-company-in-history-171743085.html",
    # META
    "https://colitco.com/meta-stock-rebound-after-sharp-drop/",
    "https://www.tipranks.com/news/meta-stock-meta-climbs-as-european-bosses-urge-eu-to-delay-damaging-ai-act",
    "https://www.stocktitan.net/news/META/meta-to-announce-second-quarter-2025-aigk0w051p9g.html",
    # TSLA
    "https://ca.news.yahoo.com/m/056d2105-248b-37d6-b6ab-41ded6dfcbed/tesla-stock-rallies-after-q2.html",
    "https://ca.finance.yahoo.com/news/jobs-shock-crashes-rate-cut-142310247.html",
    "https://finance.yahoo.com/news/tesla-tsla-stock-trades-why-164602412.html",
    # MSFT
    "https://ca.finance.yahoo.com/news/microsoft-corp-msft-pushing-more-131957198.html",
    "https://ca.finance.yahoo.com/news/microsoft-recalibrates-ai-chip-roadmap-151242246.html",
    "https://www.barchart.com/story/news/33152496/microsoft-stock-is-headed-for-4-trillion-is-it-too-late-to-buy-msft-here",
    # AMD
    "https://ca.finance.yahoo.com/news/amd-vs-micron-technology-semiconductor-155600115.html",
    "https://www.fool.com/investing/2025/07/01/why-amd-stock-jumped-28-in-june/",
    "https://www.tipranks.com/news/how-a-driver-update-helped-amd-beat-nvidia-in-one-key-race",
    # TSLA
    "https://ca.news.yahoo.com/m/056d2105-248b-37d6-b6ab-41ded6dfcbed/tesla-stock-rallies-after-q2.html",
    "https://ca.finance.yahoo.com/news/jobs-shock-crashes-rate-cut-142310247.html",
    "https://finance.yahoo.com/news/tesla-tsla-stock-trades-why-164602412.html",
    # MSFft
    "https://ca.finance.yahoo.com/news/microsoft-corp-msft-pushing-more-131957198.html",
    "https://ca.finance.yahoo.com/news/microsoft-recalibrates-ai-chip-roadmap-151242246.html",
    "https://www.barchart.com/story/news/33152496/microsoft-stock-is-headed-for-4-trillion-is-it-too-late-to-buy-msft-here",
    # AMD
    "https://ca.finance.yahoo.com/news/amd-vs-micron-technology-semiconductor-155600115.html",
    "https://www.fool.com/investing/2025/07/01/why-amd-stock-jumped-28-in-june/",
    "https://www.tipranks.com/news/how-a-driver-update-helped-amd-beat-nvidia-in-one-key-race",
    # AAPL
    "https://finance.yahoo.com/news/why-apple-aapl-stock-today-164559719.html",
    "https://finance.yahoo.com/news/apple-edges-higher-surprise-iphone-171153262.html",
    "https://finance.yahoo.com/news/apple-inc-aapl-opens-state-131952003.html",
    # PLTR
    "https://ca.finance.yahoo.com/news/palantir-technologies-inc-pltr-no-003800156.html",
    "https://ca.finance.yahoo.com/news/palantir-technologies-nasdaqgs-pltr-partners-175742202.html",
    "https://ca.finance.yahoo.com/news/palantir-technologies-nasdaqgs-pltr-powers-172716901.html",
    #CRWD
    "https://ca.news.yahoo.com/m/c3ea11af-39b8-3cef-8e3f-ce6bbd6925cd/crowdstrike-cloudflare-stock.html",
    "https://ca.finance.yahoo.com/news/crowdstrike-crwd-7-7-since-153005488.html",
    "https://ca.finance.yahoo.com/news/jim-cramer-highlights-crowdstrike-winning-162742631.html",
    # SHOP
    "https://ca.finance.yahoo.com/news/where-shopify-1-014500608.html",
    "https://ca.finance.yahoo.com/news/shopify-shop-outpaces-stock-market-214502772.html",
    "https://ca.finance.yahoo.com/news/3-reasons-buy-shopify-stock-011500514.html",
    # SPOT
    "https://ca.finance.yahoo.com/news/why-spotify-spot-dipped-more-215004116.html",
    "https://ca.finance.yahoo.com/news/investors-heavily-search-spotify-technology-130004622.html",
    "https://ca.finance.yahoo.com/news/vnet-spot-better-value-stock-154003696.html",
    # RIVN
   "https://ca.news.yahoo.com/m/9748ac40-387f-38d6-b47b-e9a5927bd02f/rivian-stock-drops-on-sales.html",
   "https://ca.finance.yahoo.com/news/rivian-lucid-benefit-trump-tax-152105553.html",
   "https://ca.finance.yahoo.com/news/rivians-q2-deliveries-dip-amid-152400919.html",
   # ZM
   "https://ca.finance.yahoo.com/news/opportunity-zoom-communications-inc-nasdaq-111154568.html",
   "https://ca.finance.yahoo.com/news/zoom-zm-expands-phone-across-065653934.html",
   "https://ca.news.yahoo.com/m/737f480f-56a6-3326-8208-0314737ee85b/zoom-communications-stock.html",
   # SQ



    # Add more URLs as needed
]

# --- LLM Summarization ---
def summarize_news_llm(headline, summary, source, date, tickers):
    prompt = f'''
Given the following news article, do the following using only information from the article:
1. Given this list of stock tickers: {', '.join(tickers)}, classify which ticker this article is about. If none, output "UNKNOWN".
2. Write a short, dashboard-friendly headline (max 12 words).
3. Write a 1-sentence blurb explaining the most important thing that happened in the article, if there are important statistics in the article, include them in the blurb.
4. Classify the news as one of: Earnings, Regulatory, Leadership, Partnership, Product, Market, Other.
5. Output as JSON: {{
  "ticker": "...",
  "headline": "...",
  "blurb": "...",
  "category": "...",
  "source": "{source}",
  "date": "{date}"
}}
---
Headline: {headline}
Article: {summary}
---
'''
    payload = {
        "model": "gemma:instruct",
        "prompt": prompt,
        "format": "json",
        "stream": False
    }
    response = requests.post(OLLAMA_API_URL, json=payload)
    response.raise_for_status()
    response_text = response.json().get('response', '{}').strip()
    return json.loads(response_text)

def store_whats_happening(supabase_client, data):
    try:
        # Delete any existing row with the same user_id, ticker, and url
        supabase_client.table("STOCK_WHATS_HAPPENING").delete() \
            .eq("user_id", data["user_id"]) \
            .eq("ticker", data["ticker"]) \
            .eq("url", data["url"]).execute()
        # Insert the new row
        response = supabase_client.table("STOCK_WHATS_HAPPENING").insert(data).execute()
        print(f"Stored what's happening for {data['ticker']}: {response}")
        return True
    except Exception as e:
        print(f"Error storing what's happening for {data['ticker']}: {e}")
        return False

def authenticate_and_get_user_id():
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    # Use the same credentials as config.py
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

if __name__ == "__main__":
    supabase, user_id = authenticate_and_get_user_id()
    for url in URLS:
        try:
            print(f"\nScraping article: {url}")
            article_data = scrape_yahoo_article(url)
            llm_result = summarize_news_llm(
                article_data["headline"],
                article_data["summary"],
                article_data["source"],
                article_data["date"],
                TICKERS
            )
            # Prepare data for Supabase
            llm_result["url"] = url
            llm_result["user_id"] = user_id
            print("\n--- LLM Output to be stored in Supabase ---")
            print(json.dumps(llm_result, indent=2, ensure_ascii=False))
            store_whats_happening(supabase, llm_result)
        except Exception as e:
            print(f"Error processing {url}: {e}") 