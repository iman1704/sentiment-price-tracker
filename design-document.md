# Sentiment-Price Tracker

## Overview
This is a dashboard application that tracks sentiments on specified public companies and visualize that as a 'sentiment score' with the
historical price of the stock. The sentiment will be based on news headlines from public apis/rss feeds that is powered by a transformer-based classifier model.

## High-level architecture

### The logic flow

1. **Ingestion layer**
    - Fetch RSS feeds
    - Deduplication check (query db for existing urls, filter out headlines thats already processed)
    - Fetch intraday stock data (5 min interval, can be changed later)
    - Output dataframe 

2. **Orchestration layer**
    - Receive dataframe from ingestion layer
    - RSS feed -> Inference layer
    - Price -> write to database
    
4. **Inference layer**
    - Receive rss feed dataframe from 
    - Runs classifier on headlines
    - Append new sentiment score and label to the dataframe
    - Output dataframe

5. **Orchestration layer**
    - Receive dataframe from inference layer
    - Write to database
    
6. **Serving layer**
    - Streamlit dashboard that queries aggregated data on-demand.

## Data sources
1. **News headlines**: google RSS feed, e.g `"https://news.google.com/rss/search?q=Maybank"`
2. **Stock price**: yfinance python library: `import yfinance as yf`

## Technology stack
**Language**: Python
**Database**: PostgreSQL
**AI/ML**: Pytorch, "mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis" from transformers library
**Orchestration**: APScheduler (Python)
**Deployment**: Docker, AWS EC2 
**Visualization**: Streamlit

## Database schema

`sentiment`

Primary key: `id`
Constraints: `UNIQUE(url)`  
Index: `ticker`, `published_at`
Columns:
- `ticker`(VARCHAR): stock ticker 
- `alias` (VARCHAR): name of company
- `headline`(TEXT): news title
- `sentiment_score`(FLOAT): model confidence
- `sentiment_label`(VARCHAR): "positive", "negative", "neutral"
- `link`(TEXT): headline link hashed for deduplication
- `published_at`(DATETIME): publication timestamp in UTC

`price`

Primary keys: `ticker`, `timestampz`
Columns:
- `ticker`(VARCHAR): stock ticker
- `close_price`(FLOAT): closing price of stock
- `volume`(BIGINT): amount of shares exchanged during the trading hours
- `timestamp`(DATETIME): timestamp of close date in UTC

### Data storage
Hot data: 30 days
Cold data: none (deleted)

## Project structure

`src/`

- `model.py`: ML model inference and logic
- `database.py`: Create database table, handle connection logic
- `config.py`: Ticker lists, API settings, DB credentials
- `ingestion.py`: Fetch RSS news and `yfinance` calls


`tests/`
- `test_ingestion.py`: validate data, deduplication, error handling
- `test_model.py`: verify model output
- `test_pipeline.py`: integration test for full flow 

`prototype.py`: proof of concept

`app.py`: streamlit frontend application

`pipeline.py`: orchestration script


## API/Interface design

### Internal data access

`ingestion.fetch_news(url_dict)`
- Input: `url_list`(dictionary of ticker, alias, url)
- Logic: fetch RSS -> filter duplicate urls -> write to dataframe
- Output: `pd.DataFrame` (`published_at`, `headline`, `link`, `ticker`)

`ingestion.fetch_price(ticker_list)`
- Input: `ticker_list` (list of ticker)
- Logic: fetch price -> reset index -> filter out non relevant data -> add ticker column-> write to dataframe
- Output: `pd.DataFrame` (`timestamp`, `ticker`, `close_price`, `volume`)

`model.classify(news_df)`
- Input: `news_df` 
- Logic: clean text -> batch process headlines
- Output: `pd.DataFrame` (Input DF + `sentiment_score`, `sentiment_label`) 

`dashboard.get_aggregated_view(ticker)`
- Input: `ticker` (str)
- Output: `pd.DataFrame` (Joined Price and Sentiment table, resampled to 1 hour interval)

## Documentation
```
"""
Module: ingestion.py

Fetches external data and handles deduplication
"""

def function(arg: str) -> pd.DataFrame:
    """
    Function summary

    Args:
        arg1 (str): description

    Returns:
        pd.DataFrame: dataframe
    """
```

## Project plan

Feasability
- [x] Verify YFinance API for price and RSS list for news
- [x] Benchmark model

Core modules
- [x] `ingestion.py`
- [x] `database.py`
- [x] `model.py`
- [x] `pipeline.py`
- [x] `app.py`

Testing
- [x] `test_ingestion.py`
- [x] `test_integration.py`

Deployment
- [x] Dockerfiles
- [x] `compose.yml`
- [ ] cloudformation template


j
