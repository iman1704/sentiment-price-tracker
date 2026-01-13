"""
Classify the rss feed headlines with sentiment and sentiment score
"""

import pandas as pd
import structlog
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer, pipeline
from transformers.models.auto.tokenization_auto import AutoTokenizer

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ]
)
logger = structlog.get_logger()


class SentimenClassifier:
    def __init__(self):
        """
        Model: "mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis"
        Quantization: Int8
        Device: CPU
        Quantization engine: qnnpack
        """
        logger.info("loading_sentiment_model")
        self.model_name = "mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis"

        try:
            # Quantization engine
            # TODO: this might need to be changed or remove to use default for specific EC2 instance
            torch.backends.quantized.engine = "qnnpack"

            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            model_fp32 = AutoModelForSequenceClassification.from_pretrained(self.model_name)

            # Apply quantization
            logger.info("quantizing_model", engine="qnnpack", dtype="qint8")
            self.model_int8 = torch.quantization.quantize_dynamic(
                model_fp32, {torch.nn.Linear}, dtype=torch.qint8
            )

            # Initialize pipeline with model
            # Uses CPU
            self.nlp_pipeline = pipeline(
                "text-classification", model=self.model_int8, tokenizer=self.tokenizer, device=-1
            )

            logger.info("model_loaded_succesfully", quantized=True)

        except Exception as e:
            logger.error("model_loading_failed", error=str(e))
            raise e

    def classify(self, news_df: pd.DataFrame) -> pd.DataFrame:
        """
        Classify the headline column


        Args:
            news_df (pd.DataFrame): dataframe fetched from rss feed (published_at, headline, ticker, alias, link)

        Return:
            pd.DataFrame containing input DataFrame + sentiment_label and sentiment_score
        """
        log = logger.bind(task="classify_sentiment")

        if news_df.empty:
            log.warning("empty_dataframe_received")
            return news_df

        try:
            headlines = news_df["headline"].tolist()
            log.info("processing_headlines", count=len(headlines))

            results = self.nlp_pipeline(headlines, truncation=True, max_length=512)

            # Calculate sentiment score (-1 to 1) from negative to positive
            scores = []
            labels = []
            for res in results:
                label = res["label"]
                confidence = res["score"]

                labels.append(label)

                # Convert model confidence to -ve for negative sentiment
                if label.lower() == "negative":
                    scores.append(confidence * -1)
                # For positive keep as is
                elif label.lower() == "positive":
                    scores.append(confidence)
                # For neutral change to 0
                else:
                    scores.append(0.0)

            # Create copy to prevent SettingWithCopy warnings
            result_df = news_df.copy()
            result_df["sentiment_label"] = labels
            result_df["sentiment_score"] = scores

            log.info("classification_complete")
            return result_df

        except Exception as e:
            log.error("classification_failed", error=str(e))
            raise e
