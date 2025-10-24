"""
Database configuration and session management using SQLAlchemy.
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# Get data directory from env or default to ./data
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# SQLite database file
DB_PATH = DATA_DIR / "patent_scores.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# Create engine with check_same_thread=False for SQLite (allows FastAPI to use it)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False  # Set to True for SQL debug logging
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for ORM models
Base = declarative_base()


def get_db():
    """
    Dependency for FastAPI routes to get a DB session.
    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database tables.
    Import models before calling this to ensure tables are registered.
    """
    from api import models  # Import here to avoid circular imports
    Base.metadata.create_all(bind=engine)
