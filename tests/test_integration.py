import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

# Dummy env config for test
os.environ["DB_URL"] = "sqlite:///:memory:"

from pipeline import Pipeline


# Mock table creation
@pytest.fixture
def mock_db_engine():
    """Creates an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")

    with engine.connect() as conn:
        conn.execute(
            text("""
            CREATE TABLE price (
                timestamp DATETIME, 
                ticker TEXT, 
                close_price FLOAT, 
                volume FLOAT,
                PRIMARY KEY (ticker, timestamp)
            )
        """)
        )
        conn.execute(
            text("""
            CREATE TABLE sentiment (
                link TEXT PRIMARY KEY, 
                headline TEXT, 
                published_at DATETIME, 
                ticker TEXT, 
                alias TEXT
            )
        """)
        )
        conn.commit()

    return engine


@pytest.fixture
def mock_pipeline(mock_db_engine):
    """
    Initializes Pipeline with mocked external dependencies
    and the in-memory database.
    """
    with (
        patch("pipeline.engine", mock_db_engine),
        patch("pipeline.init_db"),
        patch("pipeline.settings") as mock_settings,
    ):
        # Setup settings
        mock_settings.URL_DICT = {"test_source": "http://test.com/rss"}
        mock_settings.TICKER_LIST = ["AAPL"]

        pipeline = Pipeline()
        # Override the engine explicitly to ensure it uses our test DB
        pipeline.db_engine = mock_db_engine

        yield pipeline


# --- TESTS ---


def test_cold_start_run(mock_pipeline):
    """
    Scenario: First run (Empty DB).
    Expectation: Fetches data, writes to DB, updates watermark.
    """
    # 1. Setup Mock Data
    rss_data = pd.DataFrame({
        "headline": ["Test News"],
        "published_at": [datetime.now(timezone.utc)],
    })
    price_data = pd.DataFrame({
        "ticker": ["AAPL"],
        "close_price": [150.0],
        "timestamp": [datetime.now(timezone.utc)],
    })

    # 2. Patch Ingestion & Inference methods
    with (
        patch("pipeline.fetch_rss_feed", return_value=rss_data),
        patch("pipeline.fetch_price", return_value=price_data),
        patch.object(mock_pipeline.classifier, "classify", return_value=rss_data),
    ):
        # 3. Action
        mock_pipeline.run_pipeline()

    # 4. Assertions
    # Check Price written to DB
    saved_prices = pd.read_sql("SELECT * FROM price", mock_pipeline.db_engine)
    assert len(saved_prices) == 1
    assert saved_prices.iloc[0]["ticker"] == "AAPL"

    # Check State Updated
    assert mock_pipeline.latest_price_fetch is not None


def test_incremental_load_logic(mock_pipeline):
    """
    Scenario: DB has existing data.
    Expectation: Ingestion uses the DB timestamp as start_date.
    """
    # 1. Seed DB with an old timestamp (e.g., 5 days ago)
    old_date = datetime.now(timezone.utc) - timedelta(days=5)
    seed_df = pd.DataFrame({"timestamp": [old_date], "close_price": [100.0]})
    seed_df.to_sql("price", mock_pipeline.db_engine, index=False, if_exists="append")

    # Re-initialize state (simulate pipeline restart to pick up DB value)
    mock_pipeline.latest_price_fetch = mock_pipeline._get_time_mark()
    assert mock_pipeline.latest_price_fetch is not None
    expected_start_date = mock_pipeline.latest_price_fetch

    # 2. Mock Fetchers
    # We want to verify that fetch_price is called with the OLD date, not 1 year ago
    with (
        patch("pipeline.fetch_rss_feed", return_value=pd.DataFrame()),
        patch("pipeline.fetch_price", return_value=pd.DataFrame()) as mock_fetch_price,
    ):
        mock_pipeline.run_pipeline()

        # 3. Assert Arguments
        # Extract the arguments passed to fetch_price
        call_args = mock_fetch_price.call_args[1]  # kwargs
        assert call_args["start_date"] == expected_start_date
        # Ensure we didn't fallback to the 1-year buffer
        assert call_args["start_date"] > (datetime.now(timezone.utc) - timedelta(days=365))


def test_inference_failure_isolation(mock_pipeline):
    """
    Scenario: Inference layer crashes.
    Expectation: Pipeline catches error, Price is still saved, Script doesn't crash.
    """
    # 1. Setup Data
    rss_data = pd.DataFrame({"headline": ["News"], "published_at": [datetime.now(timezone.utc)]})
    price_data = pd.DataFrame({
        "ticker": ["AAPL"],
        "close_price": [155.0],
        "timestamp": [datetime.now(timezone.utc)],
    })

    # 2. Mocking
    with (
        patch("pipeline.fetch_rss_feed", return_value=rss_data),
        patch("pipeline.fetch_price", return_value=price_data),
        patch.object(mock_pipeline.classifier, "classify", side_effect=Exception("Model Exploded")),
    ):
        # 3. Action (Should not raise Exception)
        mock_pipeline.run_pipeline()

    # 4. Assertions
    # Price should still be written
    saved_prices = pd.read_sql("SELECT * FROM price", mock_pipeline.db_engine)
    assert len(saved_prices) == 1

    # Sentiment table should be empty (or not exist)
    try:
        saved_sentiments = pd.read_sql("SELECT * FROM sentiment", mock_pipeline.db_engine)
        assert len(saved_sentiments) == 0
    except Exception:
        pass  # Table might not exist, which is also correct
