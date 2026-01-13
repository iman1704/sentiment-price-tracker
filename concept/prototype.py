"""
Proof of concept code to validate these:

- data source
- feasible model
- sample model output
"""

import os
import time

import feedparser
import pandas as pd
import psutil
import torch
import yfinance as yf
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline

# MODEL_NAME = "ProsusAI/finbert"
MODEL_NAME = "mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis"

rss_urls = [
    "https://news.google.com/rss/search?q=Maybank",
    "https://news.google.com/rss/search?q=RHB",
]


class ResourceMonitor:
    """
    Helper class to monitor resources used by the model
    """

    def __init__(self, task_name):
        self.task_name = task_name
        self.process = psutil.Process(os.getpid())
        self.start_time = 0
        self.start_memory = 0

    def __enter__(self):
        # Record start time and memory (RSS in MB)
        self.start_memory = self.process.memory_info().rss / (1024 * 1024)
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        end_time = time.perf_counter()
        end_memory = self.process.memory_info().rss / (1024 * 1024)

        duration = end_time - self.start_time
        mem_diff = end_memory - self.start_memory

        print(f"\n--- [{self.task_name}] ---")
        print(f" Time Taken:      {duration:.4f} seconds")
        print(f"Start Memory:    {self.start_memory:.2f} MB")
        print(f"End Memory:      {end_memory:.2f} MB")
        print(f"Memory Growth:   {mem_diff:+.2f} MB")
        print("-" * 30)


def load_model(quantized=False):
    with ResourceMonitor("Model loading"):
        if not quantized:
            print(f"Loading unquantized model: {MODEL_NAME}")
            classifier = pipeline("sentiment-analysis", device=-1, model=MODEL_NAME)
        else:
            # Set quantization engine for Apple Silicon devices
            torch.backends.quantized.engine = "qnnpack"

            model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
            model.eval()
            model.cpu()
            tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            print("Quantizing model Float32 -> Int8")
            model = torch.quantization.quantize_dynamic(model, {torch.nn.Linear}, dtype=torch.qint8)

            # Use cpu because quantization is not yet supported on apple silicon gpu
            classifier = pipeline("sentiment-analysis", device=-1, model=model, tokenizer=tokenizer)
    return classifier


def fetch_news(urls):
    news_items = []

    for url in urls:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            news_items.append({
                "title": entry.title,
                "published": entry.published,
                "source": entry.link,
            })

    return pd.DataFrame(news_items)


def fetch_price(ticker, start_date, end_date):
    stock = yf.Ticker(ticker)
    df = stock.history(start=start_date, end=end_date)
    df = df.reset_index()

    return df


def classify(df, classifier):
    if df.empty:
        return df

    with ResourceMonitor("Inference"):
        titles = df["title"].tolist()
        start_t = time.perf_counter()
        predictions = classifier(titles)
        end_t = time.perf_counter()

        total_items = len(titles)
        print(f"Throughput: {total_items / (end_t - start_t):.2f} headlines/sec")

    df["sentiment"] = [p["label"] for p in predictions]
    df["confidence"] = [p["score"] for p in predictions]

    return df


classifier = load_model(quantized=True)

raw_data = fetch_news(rss_urls)
print(f"Fetched {len(raw_data)} headlines")

results = classify(raw_data, classifier)

# Maybank ticker in yahoo finance
prices = fetch_price("1155.KL", "2025-12-01", "2025-12-31")
print(prices.columns)
print(prices.head())
if not results.empty:
    print(results[["title", "sentiment", "confidence", "published"]].head())
else:
    print("No news")
