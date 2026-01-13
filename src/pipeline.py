"""
Pipeline module
"""

import time
from datetime import datetime, timezone

import pandas as pd
import structlog
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from config import settings
from database import Price, Sentiment, engine, init_db
from ingestion import fetch_price, fetch_rss_feed
from model import SentimenClassifier

# Logging setup
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger()


class Pipeline:
    def __init__(self):
        # Create database tables
        init_db()

        self.interval_seconds = 5 * 60  # Pipeline run interval
        self.classifier = SentimenClassifier()
        self.url_dict = settings.URL_DICT
        self.ticker_list = settings.TICKER_LIST
        self.db_engine = engine
        # To keep track of the latest price fetch to prevent redundant calls
        self.latest_price_fetch = self._get_time_mark()

    def _get_time_mark(self):
        """Helper function to get the initial time mark from db"""
        try:
            query = "SELECT MAX(timestamp) FROM price"
            result = pd.read_sql(query, self.db_engine)
            if not result.empty and result.iloc[0, 0] is not None:
                return pd.to_datetime(result.iloc[0, 0], utc=True)
        except Exception as e:
            logger.error("failed_to_fetch_initial_time_mark", error=str(e))
        return None

    def db_writer(self, df: pd.DataFrame, table_name, conflict_cols: list) -> None:
        """
        Helper function to write to database
        """
        log = logger.bind(task="db_writer", table=table_name)

        if df.empty:
            log.info("skipping_db_write", reason="dataframe_empty")
            return

        data = df.to_dict(orient="records")

        try:
            log.info("writing_to_db", row_count=len(df))
            stmt = insert(table_name).values(data)
            stmt = stmt.on_conflict_do_nothing(index_elements=conflict_cols)
            with self.db_engine.begin() as conn:
                conn.execute(stmt)
                log.info("write_successful", rows=len(data))

        except SQLAlchemyError as e:
            log.error("database_write_failed", error=str(e))

    def ingestion_layer(self) -> tuple[pd.DataFrame, pd.DataFrame, datetime]:
        """
        Fetches data

        Args:

        Returns:
            pd.DataFrame: two dataframes for RSS feed and price
            datetime: time marker to keep track of the latest price fetch
        """
        log = logger.bind(task="ingestion_layer")
        log.info("Ingestion started")

        rss_df = pd.DataFrame()
        price_df = pd.DataFrame()

        current_fetch_end = datetime.now(timezone.utc)

        try:
            # Fetch RSS feed
            log.debug("fetching_rss_feed")
            rss_df = fetch_rss_feed(url_dict=self.url_dict, db_engine=self.db_engine)

            # Fetch price based on latest fetch mark
            if self.latest_price_fetch:
                start_date = self.latest_price_fetch
            else:
                if not rss_df.empty:
                    min_rss_date = pd.to_datetime(rss_df["published_at"]).min()
                    start_date = min_rss_date - pd.DateOffset(years=1)
                else:
                    # Fallback if there are no new news, fetch based on pipeline interval
                    start_date = current_fetch_end - pd.Timedelta(seconds=self.interval_seconds)

            if start_date < current_fetch_end:
                log.debug("fetching_price_data", start=start_date, end=current_fetch_end)
                price_df = fetch_price(
                    tickers=self.ticker_list, start_date=start_date, end_date=current_fetch_end
                )
            else:
                log.info("price_data_up_to_date")

        except Exception as e:
            log.error("ingestion_failed", error=str(e))

        return rss_df, price_df, current_fetch_end

    def inference_layer(self, rss_df: pd.DataFrame) -> pd.DataFrame:
        """
        Runs classifier on RSS feed data
        """
        log = logger.bind(task="inference_layer")
        log.info("Starting new classification")

        if rss_df.empty:
            log.info("inference_skipped", reason="no_new_news_data")
            return pd.DataFrame()

        log.info("inference_started", input_rows=len(rss_df))

        try:
            classified_df = self.classifier.classify(rss_df)

            log.info("inference_completed", output_rows=len(classified_df))
            return classified_df
        except Exception as e:
            log.error("inference_failed", error=str(e))
            return pd.DataFrame()

    def run_pipeline(self):
        """
        Main execution flow
        1. Ingestion -> write price to DB
        2. Ingestion -> rss feed to Inference -> write to DB
        """
        start_time = time.time()
        log = logger.bind(task="run_pipeline")
        log.info("run_pipeline_initiated")

        rss_df, price_df, fetch_time = self.ingestion_layer()

        price_write_success = True

        if not price_df.empty:
            try:
                self.db_writer(price_df, Price, conflict_cols=["ticker", "timestamp"])
            except Exception as e:
                price_write_success = False
                log.error("price_db_write_failed", error=str(e))
        else:
            log.info("no_price_data_to_write")

        # Update time mark only if price write is successful
        # Ensures if db write fails, we retry fetching the same range
        if price_write_success:
            self.latest_price_fetch = fetch_time
            log.info("price_date_mark_updated", new_date_mark=fetch_time)
        else:
            log.warning("price_mark_update_skipped", reason="price_db_write_failed")

        # INFERENCE
        if not rss_df.empty:
            classified_df = self.inference_layer(rss_df)

            if not classified_df.empty:
                try:
                    self.db_writer(classified_df, Sentiment, conflict_cols=["link"])
                except Exception as e:
                    log.error("rss_db_write_failed", error=str(e))
            else:
                log.info("inference_returned_empty_result")
        else:
            log.info("no_rss_data_to_process")

        duration = time.time() - start_time
        log.info("run_pipeline_finished", duration=duration)

    def start(self):
        log = logger.bind(task="pipeline")
        log.info("starting_pipeline", interval=self.interval_seconds)

        while True:
            try:
                self.run_pipeline()
            except Exception as e:
                log.critical("pipeline_failure", error=str(e))

            time.sleep(self.interval_seconds)


if __name__ == "__main__":
    pipe = Pipeline()
    pipe.start()
