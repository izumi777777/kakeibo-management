from app import create_app, db
import logging

app = create_app()
with app.app_context():
    try:
        db.create_all()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database already initialized or error occurred: {e}")