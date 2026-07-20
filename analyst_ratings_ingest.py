# need to get better api https://site.financialmodelingprep.com/developer/docs/pricing
import requests
import time
from supabase import create_client
import os

# --- Configuration ---
# It's better to use environment variables for keys, but we'll hardcode for now.
# Make sure to replace YOUR_FMP_API_KEY with your actual key.
FMP_API_KEY = 
SUPABASE_URL = 
SUPABASE_KEY = 
USER_ID = 

STOCKS = ["NVDA", "META", "TSLA", "MSFT", "AMD", "AAPL", "PLTR", "CRWD", "SHOP", "SPOT", "RIVN", "ZM", "SQ"]

# --- Initialize Supabase Client ---
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
user = supabase.auth.sign_in_with_password({
    "email": 
    "password": 
})

def fetch_analyst_ratings(ticker):
    """Fetches analyst ratings and price targets from FMP."""
    url = f"https://financialmodelingprep.com/api/v3/analyst-stock-recommendations/{ticker}?apikey={FMP_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            print(f"No analyst ratings found for {ticker}.")
            return []
            
        # We only need a few fields and want to format them for our table
        ratings = []
        for r in data:
            ratings.append({
                "ticker": ticker,
                "analyst_name": r.get('analystName'),
                "rating_date": r.get('date'),
                "rating": r.get('rating'), # e.g., 'Strong Buy', 'Buy', 'Hold'
                "target_price": r.get('priceTarget'),
                "user_id": USER_ID
            })
        return ratings
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching analyst ratings for {ticker} from FMP: {e}")
        return None

def store_analyst_ratings(ratings):
    """Upserts analyst ratings into the Supabase table."""
    if not ratings:
        return False
    try:
        # Using upsert to avoid creating duplicate records on subsequent runs
        response = supabase.table("ANALYST_RATINGS").upsert(
            ratings,
            on_conflict="ticker,analyst_name,rating_date,user_id"
        ).execute()
        print(f"Successfully stored {len(ratings)} ratings.")
        return True
    except Exception as e:
        print(f"Error storing analyst ratings in Supabase: {e}")
        return False

def main():
    """Main function to process all stocks."""
    if FMP_API_KEY == "YOUR_FMP_API_KEY":
        print("ERROR: Please replace 'YOUR_FMP_API_KEY' with your actual key from financialmodelingprep.com")
        return
        
    print(f"Starting to fetch analyst ratings for {len(STOCKS)} stocks...")
    for i, ticker in enumerate(STOCKS, 1):
        print(f"\n[{i}/{len(STOCKS)}] Processing {ticker}...")

        # 1. Fetch ratings
        ratings = fetch_analyst_ratings(ticker)
        if ratings is None:
            print(f"Skipping {ticker} due to a fetch error.")
            continue
        
        # 2. Store ratings
        if ratings:
            store_analyst_ratings(ratings)

        # FMP free tier has a rate limit, let's be safe.
        if i < len(STOCKS):
            time.sleep(1) # Sleep for 1 second between requests
            
    print("\nAll stocks processed.")

if __name__ == "__main__":
    main() 
