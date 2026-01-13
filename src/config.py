"""
Get configs from env
Format: CONFIG_NAME: type = "default_value"
"""

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database Settings
    DB_URL: str
    URL_DICT: list[dict[str, str]] = [
        {
            "ticker": "1155.KL",
            "alias": "Maybank",
            "feed_url": "https://news.google.com/rss/search?q=Maybank",
        },
        {
            "ticker": "1066.KL",
            "alias": "RHB",
            "feed_url": "https://news.google.com/rss/search?q=RHB",
        },
        {
            "ticker": "6947.KL",
            "alias": "Celcomdigi",
            "feed_url": "https://news.google.com/rss/search?q=Celcomdigi",
        },
        {
            "ticker": "AMZN",
            "alias": "Amazon",
            "feed_url": "https://news.google.com/rss/search?q=Amazon",
        },
    ]
    TICKER_LIST: list = ["1155.KL", "1066.KL", "6947.KL", "AMZN"]

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


settings = Settings()
