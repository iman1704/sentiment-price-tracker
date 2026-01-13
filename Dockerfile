# 1. Base Image
FROM python:3.12-slim

# 2. Set Environment Variables
# Prevents Python from writing pyc files to disc
ENV PYTHONDONTWRITEBYTECODE=1 
# Prevents Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1 
# Do not create a virtualenv, install dependencies globally in the container
ENV POETRY_VIRTUALENVS_CREATE=false

ENV PYTHONPATH=src

# 3. System Dependencies (Required for psycopg2/Postgres)
WORKDIR /app
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 4. Install Poetry
RUN pip install --no-cache-dir poetry

# 5. Copy Dependency Files
# We copy ONLY these first to leverage Docker cache. 
# Re-installs only occur if pyproject.toml changes.
COPY pyproject.toml poetry.lock* ./

# 6. Install Dependencies
# --no-root: Do not install the project itself as a package (since we copy source later)
# --no-interaction: Do not ask for user input
RUN poetry install --no-root --no-interaction --no-ansi

# 7. Copy Application Code
COPY . .

# (Optional) Default command
CMD ["python", "app.py"]
