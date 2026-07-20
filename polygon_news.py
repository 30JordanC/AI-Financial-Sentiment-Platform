from supabase import create_client
import os
from datetime import datetime
import asyncio
import json
import re
import requests
import aiohttp
from typing import Optional

# --- CONFIGURATION ---
POLYGON_API_KEY = "BfaQ02SIQfP8piI4RK6HXgMowUHq2WDq"
OLLAMA_URL = "http://localhost:11434/api/chat"

# Supabase configuration
SUPABASE_URL = "https://cdzkowllflvoptyuvrrm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNkemtvd2xsZmx2b3B0eXV2cnJtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkxNzgzODMsImV4cCI6MjA2NDc1NDM4M30.Boe4aglV3FmFT660cWpjMopEJqHG6zTdSrmDFebukuc"  # Use your anon/public key here

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Sign in as your user (replace with your email and password)
user = supabase.auth.sign_in_with_password({
    "email": "sfloresc@caltech.edu",
    "password": "POTC33best$$"
})

MY_UUID = "c9396c7d-a75d-4d07-88bb-bc2db515cb40"  # Updated to new Supabase user UUID

def test_connection():
    """Test the connection to Supabase"""
    try:
        response = supabase.table("AI_NEWS").select("*").limit(1).execute()
        print("Successfully connected to Supabase!")
        return True
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        return False

def create_stock_summaries_table():
    """Create the AI_NEWS table in Supabase"""
    try:
        response = supabase.table("AI_NEWS").select("*").limit(1).execute()
        print("Table 'AI_NEWS' exists")
        return True
    except Exception as e:
        print(f"Error checking table: {e}")
        return False

def is_duplicate_description(ticker: str, description: str) -> bool:
    """Check if a description already exists for a ticker"""
    try:
        response = (
            supabase.table("AI_NEWS")
            .select("*")
            .eq("ticker", ticker)
            .eq("original_description", description)
            .execute()
        )
        return len(response.data) > 0
    except Exception as e:
        print(f"Error checking for duplicates: {e}")
        return False

def store_stock_summary(ticker: str, original_description: str, ai_summary: str, source_url: Optional[str] = None, news_type: Optional[str] = None):
    """Store a stock summary in Supabase"""
    print(f"Attempting to store: ticker={ticker}, original_description={original_description[:40]}, ai_summary={ai_summary[:40]}, source_url={source_url}, news_type={news_type}")
    if is_duplicate_description(ticker, original_description):
        print(f"Duplicate found for {ticker}: {original_description[:60]}... Skipping.")
        return None

    try:
        data = {
            "ticker": ticker,
            "original_description": original_description,
            "ai_summary": ai_summary,
            "source_url": source_url,
            "created_at": datetime.utcnow().isoformat(),
            "news_type": news_type,
            "user_id": MY_UUID,
        }
        print("Data to insert:", data)
        response = supabase.table("AI_NEWS").insert(data).execute()
        print("Supabase response:", response)
        print(f"Stored summary for {ticker}")
        return response.data[0]["id"] if response.data else None
    except Exception as e:
        print(f"Error storing summary: {e}")
        return None

def get_latest_summaries(ticker: Optional[str] = None, limit: int = 10):
    """Get the latest summaries for a given ticker or all tickers"""
    try:
        query = supabase.table("AI_NEWS").select("*")

        if ticker:
            query = query.eq("ticker", ticker)

        response = query.order("created_at", desc=True).limit(limit).execute()
        return response.data
    except Exception as e:
        print(f"Error retrieving summaries: {e}")
        return []

def get_polygon_news(ticker, limit=5):
    """Get news from Polygon API"""
    url = f"https://api.polygon.io/v2/reference/news?ticker={ticker}&limit={limit}&apiKey={POLYGON_API_KEY}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json().get("results", [])

def parse_summary_and_type(llm_response):
    import re
    match = re.search(r'Type:\s*(internal|external|market)', llm_response, re.IGNORECASE)
    if match:
        news_type = match.group(1).lower()
        summary = llm_response[:match.start()].strip()
    else:
        news_type = None
        summary = llm_response.strip()
    return summary, news_type

async def summarize_with_ollama(description, ticker):
    """Summarize news using Ollama via /api/chat and classify news type"""
    prompt = (
        f"Write a 50 word news summary about {ticker}. "
        "Each sentence must be complete, start with a capital letter, and not begin with a comma or incomplete phrase. "
        "Do not include any headers, titles, or markdown formatting. Just write the 4 sentences directly. "
        "After the summary, on a new line, write: 'Type: internal', 'Type: external', or 'Type: market' to classify the news as internal, external, or market news. "
        f"Context: {description}"
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            OLLAMA_URL,
            json={
                "model": "gemma:instruct",
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
            },
        ) as response:
            full_response = ""
            async for raw_chunk in response.content:
                try:
                    data = json.loads(raw_chunk)
                except json.JSONDecodeError:
                    continue

                if data.get("message") and data["message"].get("content"):
                    full_response += data["message"]["content"]

                if data.get("done"):
                    return full_response.strip()
            return None

async def process_ticker_news(ticker, limit=5):
    """Fetch, summarize, and store news for a given ticker."""
    news_items = get_polygon_news(ticker, limit)
    print(f"Found {len(news_items)} news items for {ticker}.")
    for item in news_items:
        description = item.get("description") or item.get("summary") or ""
        source_url = item.get("article_url")
        if not description:
            continue
        print(f"\nSummarizing: {description[:80]}...")
        llm_response = await summarize_with_ollama(description, ticker)
        print(f"LLM Response: {llm_response}")
        if llm_response:
            summary, news_type = parse_summary_and_type(llm_response)
            print(f"Summary: {summary}\nType: {news_type}")
            store_stock_summary(ticker, description, summary, source_url, news_type)

def clear_ticker_from_supabase(ticker: str):
    """Delete all rows for a given ticker from the AI_NEWS table in Supabase."""
    try:
        response = supabase.table("AI_NEWS").delete().eq("ticker", ticker).execute()
        print(f"Deleted {response.count if hasattr(response, 'count') else '?'} rows for ticker {ticker} from AI_NEWS.")
    except Exception as e:
        print(f"Error deleting rows for ticker {ticker}: {e}")

if __name__ == "__main__":
    # Test the connection and table
    test_connection()
    create_stock_summaries_table()

    # List of tickers to process
    TICKERS = ["NVDA", "META", "TSLA", "MSFT", "AMD", "AAPL", "PLTR", "CRWD", "SHOP", "SPOT", "RIVN", "ZM", "SQ"]

    # For each ticker: delete old news, then fetch/summarize/store new news
    for ticker in TICKERS:
        clear_ticker_from_supabase(ticker)
        asyncio.run(process_ticker_news(ticker, limit=5))

    print("All tickers processed.")
