from flask import Flask, request, jsonify
import praw

app = Flask(__name__)

# Reddit API credentials (replace with your own)
REDDIT_CLIENT_ID = 'YOUR_CLIENT_ID'
REDDIT_CLIENT_SECRET = 'YOUR_CLIENT_SECRET'
REDDIT_USER_AGENT = 'stock-scraper-script by /u/YOUR_USERNAME'

reddit = praw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT
)

@app.route('/scrape', methods=['GET'])
def scrape():
    ticker = request.args.get('ticker')
    if not ticker:
        return jsonify({'error': 'No ticker provided'}), 400

    subreddits = ['stocks', 'investing', 'wallstreetbets']
    results = []

    for subreddit in subreddits:
        try:
            for submission in reddit.subreddit(subreddit).search(ticker, limit=5):
                post_data = {
                    "subreddit": subreddit,
                    "title": submission.title,
                    "selftext": submission.selftext,
                    "author": str(submission.author),
                    "score": submission.score,
                    "num_comments": submission.num_comments,
                    "created_utc": submission.created_utc,
                    "url": submission.url,
                }
                results.append(post_data)
        except Exception as e:
            results.append({"error": f"Error searching {subreddit} for {ticker}: {e}"})

    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True) 