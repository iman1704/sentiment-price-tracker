"""
Tests for rss feed and price fetching ingestion

- expected behavior
- error handling

`uv run pytest` to run these tests
"""

import hashlib
from unittest.mock import MagicMock, patch

import pandas as pd

try:
    from ingestion import fetch_price, fetch_rss_feed
except ImportError:
    pass

# -------------------------------------------------------------------------
# TEST SUITE 1: fetch_rss_feed
# -------------------------------------------------------------------------


@patch("ingestion.pd.read_sql")
@patch("ingestion.feedparser.parse")
def test_fetch_rss_feed_logic_and_dedup(mock_parse, mock_read_sql):
    """
    Test 1: Core Logic
    - Parses RSS feed correctly.
    - Handles date parsing.
    - Performs deduplication against the DB.
    """

    # 1. Mock Feedparser (Returns 2 items)
    mock_entry_new = MagicMock(
        title="New News", link="http://news.com/new", published="2024-01-02 10:00:00"
    )
    mock_entry_old = MagicMock(
        title="Old News", link="http://news.com/old", published="2024-01-01 10:00:00"
    )
    mock_parse.return_value = MagicMock(entries=[mock_entry_new, mock_entry_old])

    old_hash = hashlib.md5("http://news.com/old".encode("utf-8")).hexdigest()
    # 2. Mock Database (Returns 1 existing link)
    # This simulates that "http://news.com/old" is already in the DB
    mock_read_sql.return_value = pd.DataFrame({"link": [old_hash]})

    # Mock Engine
    mock_engine = MagicMock()

    # Input
    url_map = [{"ticker": "1155.KL", "alias": "Maybank", "feed_url": "http://fake.url"}]

    # --- ACT ---
    result_df = fetch_rss_feed(url_map, mock_engine)

    # --- ASSERT ---

    # Should return a DataFrame
    assert isinstance(result_df, pd.DataFrame)

    # Deduplication check: Should only have 1 row (The "New News")
    assert len(result_df) == 1
    new_hash = hashlib.md5("http://news.com/new".encode("utf-8")).hexdigest()
    assert result_df.iloc[0]["link"] == new_hash

    # Schema check
    expected_cols = ["headline", "ticker", "alias", "link", "published_at"]
    assert all(col in result_df.columns for col in expected_cols)


@patch("ingestion.feedparser.parse")
def test_fetch_rss_feed_db_failure(mock_parse):
    """
    Test 2: DB Connection Failure (Fail-Open)
    - If DB connection fails, return ALL fetched items instead of crashing.
    """
    # --- ARRANGE ---
    mock_parse.return_value = MagicMock(
        entries=[
            MagicMock(title="A", link="link_a", published="2024-01-01"),
            MagicMock(title="B", link="link_b", published="2024-01-01"),
        ]
    )

    # Mock Engine to raise error on connect()
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = Exception("DB Down")

    url_map = [{"ticker": "T", "alias": "A", "feed_url": "u"}]

    # --- ACT ---
    result_df = fetch_rss_feed(url_map, mock_engine)

    # --- ASSERT ---
    # Should return all 2 items (deduplication skipped)
    assert len(result_df) == 2
    # Should not be empty
    assert not result_df.empty


@patch("ingestion.feedparser.parse")
def test_fetch_rss_feed_empty_or_error(mock_parse):
    """
    Test 3: Resilience
    - Returns empty DataFrame on network error or empty feed.
    """
    # --- ARRANGE ---
    mock_parse.side_effect = Exception("Network Error")
    mock_engine = MagicMock()
    url_map = [{"ticker": "T", "alias": "A", "feed_url": "u"}]

    # --- ACT ---
    result_df = fetch_rss_feed(url_map, mock_engine)

    # --- ASSERT ---
    assert isinstance(result_df, pd.DataFrame)
    assert result_df.empty


# -------------------------------------------------------------------------
# TEST SUITE 2: fetch_price
# -------------------------------------------------------------------------


@patch("ingestion.yf.download")
def test_fetch_price_logic_cleaning(mock_download):
    """
    Test 4: Core Logic
    - Handles multiple tickers.
    - Cleans NaN values.
    - Renames columns correctly.
    """
    # --- ARRANGE ---

    # Create a MultiIndex DataFrame to simulate yfinance output for multiple tickers
    # Structure: Columns = MultiIndex(Ticker, Attribute)
    dates = [pd.Timestamp("2024-01-01", tz="UTC"), pd.Timestamp("2024-01-02", tz="UTC")]

    # Ticker "VALID": Has data for both days
    # Ticker "DIRTY": Has None for Close on day 2
    data = {
        ("VALID", "Close"): [100.0, 101.0],
        ("VALID", "Volume"): [500, 500],
        ("DIRTY", "Close"): [200.0, None],  # NaN here
        ("DIRTY", "Volume"): [1000, 1000],
    }

    df_multi = pd.DataFrame(data, index=pd.Index(dates, name="Date"))
    df_multi.columns.names = ["Ticker", "Price"]

    # The source code calls download ONCE for all tickers
    mock_download.return_value = df_multi

    tickers = ["VALID", "DIRTY"]

    # --- ACT ---
    result_df = fetch_price(tickers, "2024-01-01", "2024-01-02")

    # --- ASSERT ---

    # Total rows should be 3 (2 from VALID + 1 valid from DIRTY)
    assert len(result_df) == 3

    # Check Column Renaming (Your code renames 'Close' -> 'close_price')
    expected_cols = ["timestamp", "ticker", "close_price", "volume"]
    assert list(result_df.columns) == expected_cols

    # Verify we dropped the NaN row for DIRTY
    dirty_rows = result_df[result_df["ticker"] == "DIRTY"]
    assert len(dirty_rows) == 1
    assert dirty_rows.iloc[0]["close_price"] == 200.0


@patch("ingestion.yf.download")
def test_fetch_price_failure(mock_download):
    """
    Test 5: Resilience
    - Returns empty DataFrame with correct columns if no data found.
    """
    # --- ARRANGE ---
    # Simulate empty dataframe return (yfinance behavior for bad ticker)
    mock_download.return_value = pd.DataFrame()

    # --- ACT ---
    result_df = fetch_price(["INVALID"], "2024-01-01", "2024-01-02")

    # --- ASSERT ---
    assert result_df.empty
    # Crucial: Must still have the correct columns so downstream code doesn't break
    expected_cols = ["timestamp", "ticker", "close", "volume"]
    assert list(result_df.columns) == expected_cols
