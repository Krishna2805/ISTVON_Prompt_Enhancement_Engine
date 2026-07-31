# demo.py - PostgreSQL Database Integration Example
import psycopg2

# Connection details for PostgreSQL
host = "localhost"
port = "5432"
dbname = "istvon_db"
username = "postgres"
password = "nife123"

try:
    # Establish connection
    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=username,
        password=password
    )
    cursor = conn.cursor()

    # Insert sample data
    insert_query = """
    INSERT INTO prompt_log (original_prompt, final_response, verdict, istvon_map_json)
    VALUES (%s, %s, %s, %s)
    """
    sample_data = ("Hello, how are you?", "I am fine, thank you.", "ALLOW", '{"I": ["Respond politely"]}')
    cursor.execute(insert_query, sample_data)

    # Commit changes
    conn.commit()
    print("✅ Sample row inserted into PostgreSQL prompt_log successfully.")

    # Clean up
    cursor.close()
    conn.close()
except Exception as e:
    print(f"PostgreSQL demo connection note: {e}")
