import requests
import json
from datetime import datetime
from supabase import create_client
import aiohttp
import asyncio
import time
# Import config values
from config import SUPABASE_URL, SUPABASE_KEY, FINNHUB_API_KEY, OLLAMA_API_URL, TICKERS, USER_EMAIL, USER_PASSWORD

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
user = supabase.auth.sign_in_with_password({
    "email": USER_EMAIL,
    "password": USER_PASSWORD
})
MY_UUID = user.user.id

def get_stock_data(symbol):
    """Fetch stock data from Finnhub API."""
    try:
        # Get quote data
        quote_url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        quote = requests.get(quote_url).json()
        
        # Get company metrics
        metrics_url = f"https://finnhub.io/api/v1/stock/metric?symbol={symbol}&metric=all&token={FINNHUB_API_KEY}"
        metrics = requests.get(metrics_url).json().get("metric", {})
        
        # Build stats dictionary
        stats = {
            "ticker": symbol,
            "price": quote.get("c"),  # Current price
            "market_cap": metrics.get("marketCapitalization"),  # In millions
            "pe_ratio": metrics.get("peNormalizedAnnual"),
            "eps_ttm": metrics.get("epsTTM"),
            "dividend_yield": metrics.get("dividendYieldIndicatedAnnual", 0) * 100,  # Convert to percentage
            "range_52w_low": metrics.get("52WeekLow"),
            "range_52w_high": metrics.get("52WeekHigh"),
            "volume_avg": metrics.get("10DayAverageTradingVolume"),
            "beta": metrics.get("beta")
        }
        
        # Validate required fields
        required_fields = ["price", "market_cap", "pe_ratio", "eps_ttm", "beta"]
        if any(stats.get(field) is None for field in required_fields):
            print(f"Warning: Missing required data for {symbol}")
            return None
            
        return stats
        
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

async def classify_financials_with_llm(stats):
    """Classify each stat as good/caution/neutral using Ollama."""
    prompt = f"""Here are the financial statistics for {stats['ticker']}:

Market Cap: ${stats['market_cap']} million
P/E Ratio: {stats['pe_ratio']}
EPS (TTM): ${stats['eps_ttm']}
Dividend Yield: {stats['dividend_yield']}%
52-Week Range: ${stats['range_52w_low']} - ${stats['range_52w_high']}
Volume (Avg): {stats['volume_avg']} million shares
Beta: {stats['beta']}
Current Price: ${stats['price']}

For each metric, classify it as either 'good', 'caution', or 'neutral' based on these guidelines:
- Market Cap: >$200B is good, <$50B is caution
- P/E Ratio: 15-25 is good, >40 is caution
- EPS: >$2 is good, <$0 is caution
- Dividend Yield: >2% is good, 0% is caution
- Beta: 0.8-1.2 is good, >2 is caution
- Volume: Higher than industry average is good

Return ONLY a JSON object with this exact structure (no other text):
{{
    "market_cap": "good/caution/neutral",
    "pe_ratio": "good/caution/neutral",
    "eps_ttm": "good/caution/neutral",
    "dividend_yield": "good/caution/neutral",
    "beta": "good/caution/neutral",
    "volume_avg": "good/caution/neutral"
}}"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                OLLAMA_API_URL,
                json={
                    "model": "gemma:instruct",
                    "prompt": prompt,
                    "stream": False,
                },
            ) as response:
                if response.status != 200:
                    print(f"Error: Ollama returned status {response.status}")
                    return {}

                result = await response.json()
                content = result.get("response", "")
                if not content:
                    print("Error: No response from Ollama")
                    return {}
                try:
                    json_start = content.find('{')
                    json_end = content.rfind('}') + 1
                    if json_start == -1 or json_end == 0:
                        print("Error: No JSON found in response")
                        return {}
                    json_str = content[json_start:json_end]
                    ratings = json.loads(json_str)
                    return ratings
                except Exception as e:
                    print(f"Error parsing JSON from response: {e}")
                    return {}
    except Exception as e:
        print(f"Error connecting to Ollama: {e}")
        return {}

async def process_stock(symbol):
    """Process a single stock: fetch data, get ratings, and store in database."""
    print(f"\nProcessing {symbol}...")
    
    # Get stock data
    stats = get_stock_data(symbol)
    if not stats:
        print(f"Skipping {symbol} due to missing data")
        return
    
    # Get ratings from LLM
    ratings = await classify_financials_with_llm(stats)
    if not ratings:
        print(f"Skipping {symbol} due to failed ratings")
        return

    # Prepare data for Supabase
    data = {
        **stats,  # Include all stats
        "market_cap_rating": ratings.get("market_cap"),
        "pe_ratio_rating": ratings.get("pe_ratio"),
        "eps_ttm_rating": ratings.get("eps_ttm"),
        "dividend_yield_rating": ratings.get("dividend_yield"),
        "volume_avg_rating": ratings.get("volume_avg"),
        "beta_rating": ratings.get("beta"),
        "user_id": MY_UUID,
        "created_at": datetime.utcnow().isoformat()
    }

    try:
        # Store new data in Supabase
        response = supabase.table("STOCK_FINANCIALS").insert(data).execute()
        print(f"Successfully stored {symbol} data in Supabase!")
        
        # Delete old rows for this ticker
        delete_response = supabase.table("STOCK_FINANCIALS") \
            .delete() \
            .eq("ticker", symbol) \
            .lt("created_at", data["created_at"]) \
            .execute()
        print(f"Deleted old rows for {symbol}")
        
    except Exception as e:
        print(f"Error with Supabase operations for {symbol}: {e}")

async def main():
    """Process all stocks with rate limiting."""
    for symbol in TICKERS:
        await process_stock(symbol)
        # Sleep for 1 second to respect API rate limits
        time.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
