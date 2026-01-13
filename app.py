"""
Frontend streamlit app - Retro Light/Office Theme
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from sqlalchemy import text

# Internal imports
from database import get_db

# -----------------------------------------------------------------------------
# Configuration & Setup
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Sentiment-Price Tracker", layout="wide", initial_sidebar_state="expanded"
)


# -----------------------------------------------------------------------------
# Retro Light Theme CSS
# -----------------------------------------------------------------------------
def inject_custom_css():
    st.markdown(
        """
        <style>
            /* Import a clean monospaced font */
            @import url('https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&display=swap');

            /* Global Styles - Light Theme */
            html, body, [class*="css"] {
                font-family: 'Courier Prime', 'Courier New', monospace;
                background-color: #f4f4f4; /* Light gray background */
                color: #222222; /* Dark gray text */
            }

            /* Headers */
            h1, h2, h3 {
                color: #000000 !important;
                text-transform: uppercase;
                border-bottom: 2px solid #000000;
                padding-bottom: 5px;
                font-weight: 700;
                letter-spacing: 1px;
            }

            /* Sidebar */
            [data-testid="stSidebar"] {
                background-color: #e0e0e0;
                border-right: 2px solid #000000;
            }
            [data-testid="stSidebar"] h1 {
                font-size: 1.2rem;
                border-bottom: 0px;
            }

            /* Inputs and Selectboxes */
            .stSelectbox div[data-baseweb="select"] > div,
            .stSlider div[data-baseweb="slider"] {
                background-color: #ffffff;
                border: 1px solid #000000;
                color: #000000;
                border-radius: 0px;
            }
            
            /* Buttons (if any) */
            button {
                border-radius: 0px !important;
                border: 2px solid #000 !important;
                background-color: #ddd !important;
                color: #000 !important;
                box-shadow: 2px 2px 0px #888;
            }

            /* Metric Containers - "Card" look */
            div[data-testid="stMetric"] {
                background-color: #ffffff;
                border: 1px solid #000000;
                padding: 10px;
                box-shadow: 4px 4px 0px #bbbbbb;
            }
            [data-testid="stMetricValue"] {
                font-size: 1.8rem !important;
                color: #000000 !important;
                font-weight: 700;
            }
            [data-testid="stMetricLabel"] {
                color: #444444 !important;
                font-weight: bold;
                text-transform: uppercase;
                font-size: 0.8rem;
            }

            /* Custom Table Styling for News */
            table {
                width: 100%;
                border-collapse: collapse;
                background-color: #ffffff;
                border: 2px solid #000000;
                font-size: 0.9rem;
            }
            th {
                background-color: #cccccc;
                color: #000000;
                text-align: left;
                padding: 12px;
                text-transform: uppercase;
                border-bottom: 2px solid #000000;
            }
            td {
                border-bottom: 1px solid #dddddd;
                padding: 10px;
                color: #333333;
            }
            tr:nth-child(even) {
                background-color: #f9f9f9;
            }
            a {
                color: #000080; /* Navy Blue */
                text-decoration: underline;
                font-weight: bold;
            }
            a:hover {
                background-color: #ffff00; /* Highlighter yellow */
                color: #000000;
            }
        </style>
    """,
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Data Access Layer
# -----------------------------------------------------------------------------


@st.cache_data(ttl=300)
def get_ticker_options():
    db = next(get_db())
    try:
        query = text(
            "SELECT DISTINCT ticker, alias FROM sentiment WHERE alias IS NOT NULL ORDER BY alias ASC"
        )
        result = db.execute(query).fetchall()
        mapping = {row.alias: row.ticker for row in result}
        return mapping
    except Exception as e:
        st.error(f"Error fetching ticker list: {e}")
        return {}
    finally:
        db.close()


def get_data_from_db(ticker: str, days: int = 30):
    db = next(get_db())
    try:
        # 1. Fetch Price Data
        price_query = text("""
            SELECT timestamp, close_price, volume
            FROM price
            WHERE ticker = :ticker
            AND timestamp >= NOW() - INTERVAL ':days days'
            ORDER BY timestamp ASC
        """)
        df_price = pd.read_sql(
            price_query,
            db.bind,
            params={"ticker": ticker, "days": days},
            parse_dates=["timestamp"],
        )

        # 2. Fetch Sentiment Data
        sentiment_query = text("""
            SELECT published_at, headline, sentiment_score, sentiment_label, link
            FROM sentiment
            WHERE ticker = :ticker
            AND published_at >= NOW() - INTERVAL ':days days'
            ORDER BY published_at ASC
        """)
        df_sentiment = pd.read_sql(
            sentiment_query,
            db.bind,
            params={"ticker": ticker, "days": days},
            parse_dates=["published_at"],
        )
        return df_price, df_sentiment
    except Exception as e:
        st.error(f"Error fetching data: {e}")
        return pd.DataFrame(), pd.DataFrame()
    finally:
        db.close()


def process_aggregated_view(df_price: pd.DataFrame, df_sentiment: pd.DataFrame):
    if df_price.empty:
        return pd.DataFrame()

    df_p = df_price.set_index("timestamp").sort_index()
    df_p_agg = df_p.resample("1h").mean()

    if not df_sentiment.empty:
        df_s = df_sentiment.set_index("published_at").sort_index()
        df_s_agg = df_s[["sentiment_score"]].resample("1h").mean()
    else:
        df_s_agg = pd.DataFrame(index=df_p_agg.index, columns=["sentiment_score"])

    combined_df = df_p_agg.join(df_s_agg, how="outer")
    return combined_df


# -----------------------------------------------------------------------------
# Visualization
# -----------------------------------------------------------------------------
def plot_dual_axis_chart(df: pd.DataFrame, ticker: str, alias: str, ma_window: int = 0):
    """
    Creates a Plotly Dual-Axis chart.
    Added: ma_window argument to plot a trend line.
    """
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Trace 1: Stock Price (Solid Navy Blue)
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["close_price"],
            name="Stock Price",
            line=dict(color="#002244", width=2),
            connectgaps=True,
        ),
        secondary_y=False,
    )

    # Trace 2: Sentiment Score (Burnt Orange/Red)
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=df["sentiment_score"],
            name="Sentiment Index",
            mode="markers",
            marker=dict(size=4, color="#cc3300"),
            line=dict(color="#cc3300", width=1.5, dash="solid"),
            connectgaps=True,
        ),
        secondary_y=True,
    )

    # --- NEW: Trace 3: Moving Average (Black Dotted Trend) ---
    if ma_window > 0:
        ma_window = ma_window * 24
        # Calculate Moving Average on the fly
        df["sent_ma"] = df["sentiment_score"].rolling(window=ma_window, min_periods=1).mean()

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["sent_ma"],
                name=f"Sentiment Trend ({ma_window}h MA)",
                mode="lines",
                # Black dotted line for "Projection/Trend" look
                line=dict(color="#000000", width=1.5, dash="dot"),
                connectgaps=True,
            ),
            secondary_y=True,
        )
    # ---------------------------------------------------------

    # Clean Layout
    fig.update_layout(
        title=dict(
            text=f"Market vs Sentiment Analysis: {alias} ({ticker})",
            font=dict(family="Courier Prime", size=16, color="black"),
        ),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(family="Courier Prime", color="black"),
            bordercolor="black",
            borderwidth=1,
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=500,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    # Axes Styling
    fig.update_xaxes(
        showgrid=True,
        gridwidth=1,
        gridcolor="#eeeeee",
        linecolor="black",
        linewidth=1,
        tickfont=dict(family="Courier Prime", color="black"),
    )

    fig.update_yaxes(
        title_text="Price (RM)",
        secondary_y=False,
        showgrid=True,
        gridwidth=1,
        gridcolor="#eeeeee",
        linecolor="black",
        linewidth=1,
        tickfont=dict(family="Courier Prime", color="#002244"),
        title_font=dict(family="Courier Prime", color="#002244"),
    )

    fig.update_yaxes(
        title_text="Sentiment Index (-1 to 1)",
        secondary_y=True,
        range=[-1.1, 1.1],
        showgrid=False,
        linecolor="black",
        linewidth=1,
        tickfont=dict(family="Courier Prime", color="#cc3300"),
        title_font=dict(family="Courier Prime", color="#cc3300"),
    )

    st.plotly_chart(fig, width="stretch")


# -----------------------------------------------------------------------------
# Main Application Logic
# -----------------------------------------------------------------------------
def main():
    inject_custom_css()

    # Sidebar
    st.sidebar.title("Parameters")
    st.sidebar.markdown("---")

    # 1. Ticker Selection
    ticker_map = get_ticker_options()

    if not ticker_map:
        st.sidebar.warning("System Alert: No tickers found in database.")
        selected_alias = None
        selected_ticker = None
    else:
        st.sidebar.markdown("**Company**")
        selected_alias = st.sidebar.selectbox(
            "Select Company", options=list(ticker_map.keys()), label_visibility="collapsed"
        )
        selected_ticker = ticker_map[selected_alias]

    st.sidebar.markdown("**Timeframe (Days)**")
    time_range = st.sidebar.slider(
        "Lookback Period", min_value=1, max_value=30, value=7, label_visibility="collapsed"
    )

    # Moving Average
    st.sidebar.markdown("**Moving Average**")
    show_ma = st.sidebar.checkbox("Show sentiment score MA", value=False)
    ma_window = 0
    if show_ma:
        ma_window = st.sidebar.slider("MA Window (Days)", 1, 60, 6)

    st.sidebar.markdown("---")
    st.sidebar.text(f"Ticker: {selected_ticker if selected_ticker else 'N/A'}")

    # Main Header
    st.title("Sentiment-Price Tracker")
    st.markdown("Tracks news sentiments with stock price")

    if selected_alias:
        st.markdown(f"Retrieving data for **{selected_alias}** [{selected_ticker}]...")

        with st.spinner(f"Querying database..."):
            df_price_raw, df_news_raw = get_data_from_db(selected_ticker, days=time_range)

        if df_price_raw.empty:
            st.warning(f"Notice: No price records found for {selected_ticker}.")
        else:
            # 2. Key Metrics
            latest_price = df_price_raw.iloc[-1]["close_price"]

            if not df_news_raw.empty:
                last_24h = df_news_raw[
                    df_news_raw["published_at"]
                    > (df_news_raw["published_at"].max() - pd.Timedelta(hours=24))
                ]
                avg_sent_24h = last_24h["sentiment_score"].mean() if not last_24h.empty else 0.0
            else:
                avg_sent_24h = 0.0

            # Metrics
            col1, col2, col3 = st.columns(3)
            col1.metric("Latest Price", f"{latest_price:.2f}")
            col2.metric("24h Sentiment Score", f"{avg_sent_24h:.2f}")
            col3.metric("Total Headlines", len(df_news_raw))

            st.markdown("---")

            # 3. Process & Visualize
            agg_df = process_aggregated_view(df_price_raw, df_news_raw)
            plot_dual_axis_chart(agg_df, selected_ticker, selected_alias, ma_window)

            # 4. Detailed News View
            st.subheader("News Archive")

            if not df_news_raw.empty:
                display_news = df_news_raw.copy()
                display_news = display_news.sort_values(by="published_at", ascending=False)

                # Simple text arrow for link
                display_news["headline"] = display_news["headline"]

                # Clean styling for sentiment
                def color_sentiment(val):
                    if val == "positive":
                        return "color: #006600; font-weight: bold;"  # Dark Green
                    elif val == "negative":
                        return "color: #cc0000; font-weight: bold;"  # Dark Red
                    return "color: #666666;"

                st.markdown(
                    display_news[["published_at", "headline", "sentiment_label", "sentiment_score"]]
                    .style.format({"sentiment_score": "{:.2f}"})
                    .map(color_sentiment, subset=["sentiment_label"])
                    .hide()
                    .to_html(escape=False),
                    unsafe_allow_html=True,
                )
            else:
                st.info("No relevant news items found for the selected period.")


if __name__ == "__main__":
    main()
