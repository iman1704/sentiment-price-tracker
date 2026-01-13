import json

import psycopg2
from psycopg2.extras import RealDictCursor


# DB_HOST=db
# DB_PORT=5432
# DB_USER=user
# DB_PASSWORD=password
# DB_NAME=sentiment_db
# DB_URL=postgresql://user:password@db:5432/sentiment_db
def query_to_json():
    # Connection details - adjust these to match your Docker setup
    conn_params = {
        "host": "localhost",
        "database": "sentiment_db",
        "user": "user",
        "password": "password",
        "port": 5432,
    }

    try:
        # Connect to the database
        conn = psycopg2.connect(**conn_params)

        # RealDictCursor allows us to fetch rows as dictionaries (key: value)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Execute your query
        query = "SELECT * FROM sentiment LIMIT 5;"
        cur.execute(query)

        # Fetch all results
        results = cur.fetchall()

        # Convert to JSON string
        json_output = json.dumps(results, indent=4, default=str)

        # Print or save the output
        print(json_output)

        cur.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    query_to_json()
