# Sentiment-Price Tracker

## Project summary
Use news as a sentiment source and track it with the latest stock price of specified public companies

## Project architecture

**Database**: PostgreSQL
**ML Model**:
**Deployment**: Docker, AWS EC2
Tests driven

## Project structure

`src/`
- `preprocessing.py`: Data processing (Cleaning, verify, etc..)
- `model.py`: ML model inference and logic
- `database.py`: Database connection handler
- `config.py`: General config
- `ingestion.py`: Fetch data


`tests/`
- `ingestion.py`: test data ingestion (reachable, data validity)
- `model.py`: test model output
- `preprocessing.py`: test data processing, validate output

`prototype.py`: proof of concept
`app.py`: frontend application
`pipeline.py`: pipeline script

