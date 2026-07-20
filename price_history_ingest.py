import requests
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client
import time
# Import config values
from config import SUPABASE_URL, SUPABASE_KEY, POLYGON_API_KEY, TICKERS, USER_EMAIL, USER_PASSWORD

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
user = supabase.auth.sign_in_with_password({
    "email": USER_EMAIL,
    "password": USER_PASSWORD
})
USER_ID = user.user.id

# Use TICKERS from config

# Just test with NVDA first
# STOCKS = ["NVDA", "META", "TSLA", "MSFT", "AMD", "AAPL", "PLTR", "CRWD", "SHOP", "SPOT", "RIVN", "ZM", "SQ"]


def delete_stock_data(symbol):
    """
    Delete all existing data for a given stock symbol.
    
    Args:
        symbol (str): Stock ticker symbol
    """
    try:
        response = supabase.table("STOCK_PRICE_HISTORY") \
            .delete() \
            .eq("ticker", symbol) \
            .eq("user_id", USER_ID) \
            .execute()
        print(f"Deleted existing data for {symbol}")
        return True
    except Exception as e:
        print(f"Error deleting data for {symbol}: {e}")
        return False

def fetch_historical_data(symbol, start_date=None, end_date=None):
    """
    Fetch historical OHLCV data for a given stock using Polygon.io API.
    
    Args:
        symbol (str): Stock ticker symbol
        start_date (str, optional): Start date in YYYY-MM-DD format
        end_date (str, optional): End date in YYYY-MM-DD format
    """
    try:
        # Set end_date to today (June 19, 2025)
        if not end_date:
            end_date = "2025-06-19"
        if not start_date:
            # Get last 30 days of data
            start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=30)).strftime('%Y-%m-%d')

        # Fetch data from Polygon.io
        url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{start_date}/{end_date}"
        params = {
            "apiKey": POLYGON_API_KEY,
            "sort": "desc",  # Get newest data first
            "limit": 50000  # Maximum limit to get all data
        }
        
        print(f"Fetching data for {symbol} from {start_date} to {end_date}...")
        response = requests.get(url, params=params)
        data = response.json()
        
        if response.status_code != 200:
            print(f"HTTP Error {response.status_code} for {symbol}: {response.text}")
            return None
        
        if data.get('resultsCount', 0) == 0:
            print(f"No data found for {symbol}")
            return None
            
        # Convert to DataFrame
        results = data.get('results', [])
        df = pd.DataFrame(results)
        
        # Rename columns to match our schema
        df = df.rename(columns={
            'o': 'open',
            'h': 'high',
            'l': 'low',
            'c': 'close',
            'v': 'volume',
            't': 'timestamp'
        })
        
        # Convert timestamp from milliseconds to date
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date.astype(str)
        
        # Add ticker column
        df['ticker'] = symbol
        
        # Add created_at column with current UTC timestamp
        df['created_at'] = datetime.utcnow().isoformat()

        # Add user_id column for RLS
        df['user_id'] = USER_ID
        
        # Convert volume to numeric string to ensure precision
        df['volume'] = df['volume'].astype(str)
        
        # Select and reorder columns to match our schema
        df = df[['ticker', 'date', 'open', 'high', 'low', 'close', 'volume', 'created_at', 'user_id']]
        
        # Print sample of processed data
        print("\nSample of processed data:")
        print(df.head())
        
        return df
        
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        print(f"Full error: {str(e)}")
        return None

def store_price_history(df):
    """
    Store price history data in Supabase.
    
    Args:
        df (pandas.DataFrame): DataFrame containing OHLCV data
    """
    if df is None or df.empty:
        return False
        
    try:
        # Convert DataFrame to list of dictionaries
        records = df.to_dict('records')
        
        print(f"\nAttempting to store {len(records)} records...")
        
        # Store in batches of 100 to avoid request size limits
        batch_size = 100
        total_stored = 0
        
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            
            try:
                # Insert new data
                response = supabase.table("STOCK_PRICE_HISTORY").insert(batch).execute()
                
                batch_stored = len(batch)
                total_stored += batch_stored
                print(f"Stored batch of {batch_stored} records (Total: {total_stored}/{len(records)})")
                
            except Exception as e:
                print(f"Error storing batch: {e}")
                continue
            
        print(f"\nSuccessfully stored {total_stored} out of {len(records)} records")
        return total_stored > 0
        
    except Exception as e:
        print(f"Error storing data in Supabase: {e}")
        return False

def process_stock(symbol):
    """Process historical data for a single stock."""
    print(f"\nProcessing historical data for {symbol}...")
    
    # First delete existing data
    if not delete_stock_data(symbol):
        print(f"Warning: Failed to delete old data for {symbol}")
    
    # Fetch historical data
    df = fetch_historical_data(symbol)
    if df is not None:
        print(f"Fetched {len(df)} days of data for {symbol}")
        
        # Store in Supabase
        if store_price_history(df):
            print(f"Successfully stored historical data for {symbol}")
        else:
            print(f"Failed to store historical data for {symbol}")
    else:
        print(f"Failed to fetch historical data for {symbol}")

def main():
    """Process historical data for all stocks with rate limiting."""
    total_stocks = len(TICKERS)
    successful = 0
    failed = 0
    
    print(f"\nStarting data ingestion for {total_stocks} stocks...")
    
    for i, symbol in enumerate(TICKERS, 1):
        print(f"\n[{i}/{total_stocks}] Processing {symbol}...")
        
        try:
            process_stock(symbol)
            successful += 1
            
            # Sleep for 12 seconds between stocks to respect rate limit (5 calls per minute)
            if i < total_stocks:  # Don't sleep after the last stock
                print(f"Waiting 12 seconds before next stock (rate limiting)...")
                time.sleep(12)
                
        except Exception as e:
            print(f"Failed to process {symbol}: {e}")
            failed += 1
            
            # Still wait before next stock even if this one failed
            if i < total_stocks:
                print(f"Waiting 12 seconds before next stock (rate limiting)...")
                time.sleep(12)
    
    print(f"\nProcessing complete!")
    print(f"Successfully processed: {successful}/{total_stocks} stocks")
    if failed > 0:
        print(f"Failed to process: {failed} stocks")

if __name__ == "__main__":
    main() 