import requests
import time
from supabase import create_client
import json
# Import config values
from config import SUPABASE_URL, SUPABASE_KEY, OLLAMA_API_URL, POLYGON_API_KEY, TICKERS, USER_EMAIL, USER_PASSWORD

# --- Configuration ---
# (All config now comes from config.py)

# Remove old STOCKS, POLYGON_API_KEY, SUPABASE_URL, SUPABASE_KEY, OLLAMA_API_URL

# Use TICKERS from config


def fetch_company_details(ticker):
    """Fetches company name and description from Polygon.io."""
    url = f"https://api.polygon.io/v3/reference/tickers/{ticker}?apiKey={POLYGON_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        results = data.get('results', {})
        return {
            "name": results.get('name'),
            "description": results.get('description')
        }
    except requests.exceptions.RequestException as e:
        print(f"Error fetching details for {ticker} from Polygon: {e}")
        return None

def generate_ai_content(description, company_name):
    """Generates an AI summary and hashtags using a local Ollama server."""
    if not description or not company_name:
        return None, None

    prompt = f"""
Analyze the following company description for {company_name} and generate two things in JSON format:
1. A summary for an "AI Intelligence Brief" section in a financial app.
2. A list of 4-5 relevant, single-word, lowercase hashtags.

**Instructions for AI Brief:**
- **Goal**: Condense the most critical company information into a powerful, insightful summary for a financial analyst.
- **Length**: Strictly adhere to a **maximum of three sentences**.
- **Style**: Professional, insightful, and concise.
- **Content**: Start with a strong opening statement identifying the company's core identity. Mention its role in technology or its specific industry, key business drivers (like cloud-native architecture for CrowdStrike), and recent performance catalysts if mentioned in the text.
- **Format**: A single, dense paragraph. Do not use lists or bullet points.
- **Tone**: Forward-looking and confident.

**Instructions for Hashtags:**
- Provide a JSON array of 4-5 strings.
- Each string should be a single, relevant, lowercase keyword (e.g., "cybersecurity", "cloud", "saas").

**Source Description for {company_name}:**
---
{description}
---

**Example Output Format (should be a single JSON object):**
{{
  "ai_summary": "NVIDIA Corporation is a global technology leader known for its innovative products and services. Leading AI chip maker experiencing explosive growth from datacenter demand. Recent partnerships with major cloud providers and strong Q4 earnings beat expectations by 15%. AI revolution driving unprecedented demand.",
  "hashtags": ["#ai", "#semiconductor", "#datacenter", "#gpu"]
}}

Generate the JSON output for {company_name} based on the provided source description.
"""
    try:
        payload = {
            "model": "gemma:instruct",
            "prompt": prompt,
            "format": "json", # Request JSON format directly
            "stream": False
        }
        response = requests.post(OLLAMA_API_URL, json=payload)
        response.raise_for_status()
        
        # The 'response' field from Ollama contains a JSON *string*, so we need to parse it.
        response_text = response.json().get('response', '{}').strip()
        content_json = json.loads(response_text)
        
        ai_summary = content_json.get('ai_summary')
        hashtags = content_json.get('hashtags')
        
        return ai_summary, hashtags

    except requests.exceptions.RequestException as e:
        print(f"Error connecting to Ollama server: {e}")
        print("Please ensure your local Ollama server is running and accessible.")
        return None, None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response from Ollama: {e}")
        print(f"Received text: {response.text}")
        return None, None

def store_company_profile(supabase_client, data):
    """Deletes any existing profile for the ticker/user_id, then inserts the new one."""
    try:
        # Delete existing row
        supabase_client.table("COMPANY_PROFILES").delete().eq("ticker", data["ticker"]).eq("user_id", data["user_id"]).execute()
        # Insert new row
        response = supabase_client.table("COMPANY_PROFILES").insert(data).execute()
        print(f"Supabase response for {data['ticker']}: {response}")
        print(f"Successfully stored profile for {data['ticker']}.")
        return True
    except Exception as e:
        print(f"Error storing profile for {data['ticker']} in Supabase: {e}")
        return False

def search_polygon_ticker(query):
    url = f"https://api.polygon.io/v3/reference/tickers?search={query}&active=true&apiKey={POLYGON_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error searching for ticker '{query}': {e}")

def main():
    """Main function to process all stocks."""
    
    # Initialize the client within the main execution block
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # --- Authenticate User and Get User ID ---
    # This step is crucial. It configures the supabase client instance
    # with the user's auth token for all subsequent requests.
    try:
        auth_response = supabase.auth.sign_in_with_password({
            "email": USER_EMAIL,
            "password": USER_PASSWORD
        })
        user_id = auth_response.user.id
        print(f"Successfully authenticated user: {user_id}")
    except Exception as e:
        print(f"Fatal Error: Could not authenticate with Supabase. {e}")
        print("Please check credentials. The script cannot proceed.")
        return

    print(f"\nStarting to process {len(TICKERS)} stocks for AI summaries...")
    for i, ticker in enumerate(TICKERS, 1):
        print(f"\n[{i}/{len(TICKERS)}] Processing {ticker}...")

        # 1. Fetch company details
        details = fetch_company_details(ticker)
        if not details or not details.get('description'):
            print(f"Could not fetch details for {ticker}. Skipping.")
            continue
        
        print(f"Fetched details for {details['name']}.")

        # 2. Generate AI Content
        ai_summary, hashtags = generate_ai_content(details['description'], details['name'])
        if not ai_summary or not hashtags:
            print(f"Could not generate AI content for {ticker}. Skipping.")
            continue
            
        print("Generated AI summary and hashtags.")

        # 3. Store in Supabase
        profile_data = {
            "ticker": ticker,
            "company_name": details['name'],
            "description": details['description'],
            "ai_summary": ai_summary,
            "hashtags": hashtags,
            "user_id": user_id  # Use the dynamic user_id from the authenticated session
        }
        print("\n--- Data to be stored in Supabase ---")
        print(json.dumps(profile_data, indent=2, default=str))
        store_company_profile(supabase, profile_data)

        # Respect Polygon API rate limit (5 calls/minute)
        if i < len(TICKERS):
            print("Waiting 13 seconds before next request...")
            time.sleep(13)
            
    print("\nAll stocks processed.")

if __name__ == "__main__":
    # --- COMMENT OUT PREVIOUS SQ TEST ---
    # print("\n--- Testing fetch_company_details for 'SQ' ---")
    # sq_details = fetch_company_details("SQ")
    # if sq_details:
    #     print("Success! Details for SQ:")
    #     print(json.dumps(sq_details, indent=2, ensure_ascii=False))
    # else:
    #     print("No details found for SQ.")

    # --- MAIN PROCESSING CODE ---
    main() 