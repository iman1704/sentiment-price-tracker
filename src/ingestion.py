"""
Ingest and extract data from news feed and stock price

- scrape data from rss feed
- get stock price from yahoo finance
- output these data to the database
"""

import hashlib

import feedparser
import pandas as pd
import structlog
import yfinance as yf
from dateutil import parser
from sqlalchemy import bindparam, text

# Logging setup
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger()


def fetch_rss_feed(url_dict, db_engine) -> pd.DataFrame:
    """
    Get news headline, published date, link from google news rss feed
    e.g "https://news.google.com/rss/search?q=Maybank"

    args:
        url_dict (list): list of dictionaries containing ticker name, alias, rss feed urls
                        e.g [{"ticker": "1155.KL", "alias": "Maybank", "feed_url": "https://news.google.com/rss/search?q=Maybank"}]
        db_engine: SQLAlchemy engine object

    return:
        pd.DataFrame containing published_at, headline, ticker, alias, link
    """
    log = logger.bind(task="fetch_rss_feed")
    news_item = []

    try:
        for item in url_dict:
            ticker = item["ticker"]
            alias = item["alias"]
            url = item["feed_url"]

            feed = feedparser.parse(url)

            for entry in feed.entries:
                try:
                    pub_date = parser.parse(entry.published)
                except:
                    pub_date = pd.Timestamp.now(tz="UTC")

                ori_link = entry.link

                hashed_link = hashlib.md5(ori_link.encode("utf-8")).hexdigest()

                news_item.append({
                    "headline": entry.title,
                    "ticker": ticker,
                    "alias": alias,
                    "link": hashed_link,
                    "published_at": pub_date,
                })

        if not news_item:
            log.warning("no_rss_items_found")
            return pd.DataFrame()

        df_new = pd.DataFrame(news_item)
        df_new["published_at"] = pd.to_datetime(df_new["published_at"], utc=True)

    except Exception as e:
        log.exception("rss_fetch_failed", error=str(e))
        return pd.DataFrame()

    # Deduplication
    try:
        links_to_check = tuple(df_new["link"].unique())

        if not links_to_check:
            return pd.DataFrame()

        # Query table
        query = text(f"SELECT link FROM sentiment WHERE link IN :link")
        query = query.bindparams(bindparam("link", expanding=True))

        with db_engine.connect() as conn:
            existing_links_df = pd.read_sql(query, conn, params={"link": links_to_check})

        existing_links_set = set(existing_links_df["link"].tolist())

        df_final = df_new[~df_new["link"].isin(existing_links_set)].copy()

        log.info(
            "deduplication_complete",
            fetched=len(df_new),
            duplicates=len(existing_links_df),
            news_item=len(df_final),
        )

        return df_final

    except Exception as e:
        # If DB check fails (e.g table doesn't exist), return all
        log.error("deduplication_failed_returning_all", error=str(e))
        return df_new


def fetch_price(tickers, start_date, end_date) -> pd.DataFrame:
    """
    Get ticker price from yahoo finance

    args:
        ticker (list): stock ticker
        start_date : starting date for ticker price
        end_date: end date for ticker price

    return:
        pd.DataFrame: DataFrame containing timestamp, ticker, close, volume
    """
    log = logger.bind(task="fetch_price")

    if not tickers:
        return pd.DataFrame(columns=["timestamp", "ticker", "close", "volume"])

    # Ensure list does not contain duplicates
    tickers = list(set(tickers))

    # Download price data in batch
    try:
        raw_data = yf.download(
            tickers, start=start_date, end=end_date, group_by="ticker", progress=False, threads=True
        )
    except Exception as e:
        log.error("price_fetch_failed", error=str(e))
        return pd.DataFrame(columns=["timestamp", "ticker", "close", "volume"])

    if raw_data.empty:
        log.warning("price_fetch_returned_empty")
        return pd.DataFrame(columns=["timestamp", "ticker", "close", "volume"])

    is_multi_index = isinstance(raw_data.columns, pd.MultiIndex)
    # Iterate through each ticker
    dfs = []
    for t in tickers:
        try:
            if is_multi_index:
                if t in raw_data.columns.get_level_values(0):
                    df = raw_data[t].copy()
                else:
                    continue
            else:
                if len(tickers) == 1 and tickers[0] == t:
                    df = raw_data.copy()
                else:
                    continue

            if df.empty or df["Close"].isna().all():
                log.warning("ticker_data_empty_or_nan", ticker=t)
                continue

            df = df.dropna(subset=["Close"])

            # Reset index so Date becomes a column
            df = df.reset_index()
            # Add ticker column
            df["ticker"] = t

            # Rename columns
            target_cols = {"Date": "timestamp", "Close": "close_price", "Volume": "volume"}
            df = df.rename(columns=target_cols)

            try:
                # Keep only columns we want
                df = df[["timestamp", "ticker", "close_price", "volume"]]
            except KeyError as e:
                log.warning("column_missing", columns=df.columns.tolist(), ticker=t)
                continue

            dfs.append(df)

        except KeyError as e:
            log.warning("processing_failed_key_error", ticker=t, error=str(e))
            continue
        except Exception as e:
            log.error("processing_failed", ticker=t, error=str(e))
            continue

    if not dfs:
        log.warning("no_valid_data_extracted")
        return pd.DataFrame(columns=["timestamp", "ticker", "close_price", "volume"])

    # Consolidate
    final_df = pd.concat(dfs, ignore_index=True)
    # Standardize timezone
    final_df["timestamp"] = pd.to_datetime(final_df["timestamp"], utc=True)
    log.info("price_fetch_success", total_rows=len(final_df))
    return final_df
