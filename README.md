## What is this?
**Sentiment-Price Tracker** is a dashboard application designed to track sentiments regarding specific public companies and visualize that data alongside historical stock prices. 

The application ingests news headlines from public RSS feeds and processes them using a Transformer-based classifier model (DistilRoBERTa) to generate a sentiment score. This score is then overlaid with intraday stock data fetched via `yfinance` to help visualize potential correlations between news sentiment and market movement.

## How to run it

### Prerequisites
*   Docker & Docker Compose
*   Python 3.x (if running locally without Docker)

### Installation
1.  **Clone the repository**
    ```bash
    git clone https://github.com/iman1704/sentiment-price-tracker.git
    cd sentiment-price-tracker
    ```

2.  **Configuration**
    *   Review `src/config.py` to configure ticker lists, API settings, and database credentials.
    *   Optionally use these configs with a `.env` file

3.  **Run with Docker (Recommended)**
    Build and start the services (Database, Pipeline, and Dashboard):
    ```bash
    docker compose up --build
    ```

4.  **Access the Dashboard**
    Open your browser and navigate to:
    `http://localhost:8501` (Default Streamlit port)

## Features
*   **Automated Data Ingestion**: Fetches Google News RSS feeds and intraday stock data (5-minute intervals) using `yfinance`.
*   **Smart Deduplication**: Checks existing URLs in the database to prevent processing the same headline twice.
*   **Sentiment Classification**: Utilizes `mrm8488/distilroberta-finetuned-financial-news-sentiment-analysis` via the Transformers library to classify headlines as Positive, Negative, or Neutral.
*   **Persistent Storage**: Stores sentiment scores and price history in a PostgreSQL database (retaining 30 days of hot data).
*   **Interactive Visualization**: Streamlit dashboard that allows users to query aggregated data on-demand.

## Screenshots
![Image1](snaps/dashboard.png)

## Project architecture

### Technology Stack
*   **Language**: Python
*   **Frontend**: Streamlit
*   **Database**: PostgreSQL
*   **ML Framework**: PyTorch / HuggingFace Transformers
*   **Orchestration**: APScheduler
*   **Deployment**: Docker Compose

### Logic Flow
1.  **Ingestion Layer**: Fetches raw RSS feeds and stock data. Handles URL deduplication against the database.
2.  **Inference Layer**: Runs the DistilRoBERTa model on new headlines to append sentiment scores and labels.
3.  **Orchestration Layer**: Manages the flow of data between ingestion, inference, and the database using APScheduler.
4.  **Serving Layer**: A Streamlit application queries the database to display an aggregated view (resampled to 1-hour intervals) of price vs. sentiment.

### File Structure
*   `src/`: Core logic modules (`ingestion.py`, `model.py`, `database.py`, `config.py`).
*   `tests/`: Unit and integration tests (`test_ingestion.py`, `test_integration.py`).
*   `app.py`: The Streamlit frontend entry point.
*   `pipeline.py`: The orchestration script for data updates.
*   `compose.yml`: Docker services definition.
