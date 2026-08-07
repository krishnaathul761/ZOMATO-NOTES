import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./zomato_notes.db")

# SQLite requires check_same_thread=False for FastAPI's async context
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
else:
    # PostgreSQL (Supabase) — force IPv4 to avoid IPv6 issues on Render free tier
    # Also add connection pool settings suitable for a single free instance
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,          # test connection before using from pool
        pool_recycle=300,            # recycle connections every 5 minutes
        connect_args={
            "options": "-c statement_timeout=30000",   # 30s query timeout
            "connect_timeout": 10,                     # 10s connection timeout
        },
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency: yields a DB session and ensures it is closed after each request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
