# demo.py - PostgreSQL Database Integration Example
from database import DatabaseManager, HAS_PSYCOPG2


def main():
    """Demonstrate PostgreSQL prompt_log setup and insertion via DatabaseManager."""
    if not HAS_PSYCOPG2:
        print("PostgreSQL demo note: psycopg2 is not installed. Skipping database insertion.")
        return

    db = DatabaseManager()
    try:
        logged = db.log_transformation(
            original_prompt="Hello, how are you?",
            istvon_json={"I": ["Respond politely"]},
            success=True,
            verdict="ALLOW",
            reason="Demo entry",
            response="I am fine, thank you.",
        )
        if logged:
            print("✅ Sample row inserted into PostgreSQL prompt_log successfully.")
        else:
            print("PostgreSQL demo note: Database unavailable or unconfigured; skipped insertion.")
    finally:
        db.close_connection()


if __name__ == "__main__":
    main()

