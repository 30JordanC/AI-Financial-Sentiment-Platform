import feedparser
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

QUERIES = [
    "nvidia stock news",
    "tesla stock news",
    # Add more queries as needed
]

MAX_RESULTS = 5

def get_google_news_urls(query, max_results=5):
    rss_url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}"
    feed = feedparser.parse(rss_url)
    urls = [entry.link for entry in feed.entries[:max_results]]
    return urls

def resolve_google_news_url(url):
    try:
        resp = requests.get(url, allow_redirects=True, timeout=10)
        return resp.url
    except Exception as e:
        print(f"Error resolving Google News URL: {e}")
        return url

def get_real_url_with_selenium(google_news_url):
    options = Options()
    options.headless = True
    driver = webdriver.Chrome(options=options)
    driver.get(google_news_url)
    real_url = driver.current_url
    driver.quit()
    return real_url

if __name__ == "__main__":
    for query in QUERIES:
        print(f"\nTop {MAX_RESULTS} news URLs for query: '{query}'")
        urls = get_google_news_urls(query, max_results=MAX_RESULTS)
        for url in urls:
            real_url = get_real_url_with_selenium(url)
            print(f"Google News URL: {url}")
            print(f"Resolved Article URL (Selenium): {real_url}\n") 