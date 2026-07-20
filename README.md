# AI-Financial-Sentiment-Platform
An AI-powered backend system that collects financial discussions from Reddit and X (Twitter), processes them through NLP models, and generates community sentiment scores for investment research.

## Features

- Collects financial discussions from social media
- Cleans and filters irrelevant content
- Uses Ollama LLMs for summarization
- Generates sentiment scores
- Stores processed data in SQL
- Optimized backend data pipeline

## Tech Stack

- Python
- SQL
- Ollama
- Pandas
- Requests
- FastAPI (if applicable)

## Architecture

Reddit/X
      ↓
Data Collection
      ↓
Cleaning
      ↓
Ollama NLP
      ↓
Sentiment Analysis
      ↓
SQL Database
      ↓
API / Dashboard

## Example Output

Ticker: NVDA

Sentiment Score: +0.83

Summary:
"Most users remain bullish following earnings due to strong AI demand."

Confidence: 91%

## Installation

```bash
git clone https://github.com/30JordanC/ai-financial-sentiment-platform.git

cd ai-financial-sentiment-platform

pip install -r requirements.txt
