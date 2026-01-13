"""
Database utility

- Defines table schema
- Create defined table
- Handles connection
"""

import time

import structlog
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger()

engine = create_engine(settings.DB_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Database schema
class Sentiment(Base):
    __tablename__ = "sentiment"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), nullable=False)
    alias = Column(String(40), nullable=False)
    headline = Column(Text, nullable=False)
    sentiment_score = Column(Float, nullable=False)
    sentiment_label = Column(String(10), nullable=False)
    link = Column(Text, nullable=True, unique=True)
    published_at = Column(DateTime, nullable=False)

    # __table_args__ = Index("idx_ticker_published", "ticker", "published_at")


class Price(Base):
    __tablename__ = "price"

    ticker = Column(String(10), primary_key=True, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=False)
    timestamp = Column(DateTime, primary_key=True, nullable=False)


# Create table
def init_db():
    log = logger.bind(task="db_setup")

    # OPTIMIZE: more robust retry logic
    retries = 5
    while retries > 0:
        try:
            Base.metadata.create_all(bind=engine)
            log.info("db_table_setup_successful")
            break
        except OperationalError as e:
            log.exception("db_table_setup_failed", error=str(e))
            time.sleep(2)
            retries -= 1


# Connection helper
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
