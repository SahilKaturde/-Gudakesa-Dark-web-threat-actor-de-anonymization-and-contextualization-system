import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# Determine if offline database mode is enabled
use_offline = os.getenv("USE_OFFLINE_DB", "true").lower() in ("true", "1", "yes")

if use_offline:
    # Use OFFLINE_DATABASE_URL or build local PostgreSQL connection URL
    offline_url = os.getenv("OFFLINE_DATABASE_URL")
    if not offline_url:
        db_user = os.getenv("DB_USER", "postgres")
        db_pass = os.getenv("DB_PASSWORD", "sahil@1234").replace("@", "%40")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "Darkweb_intel")
        offline_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    DATABASE_URL = offline_url
else:
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "sqlite:///./gudakesa_offline.db"
    )

# Select engine driver based on URL scheme
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    db_url = DATABASE_URL
    if db_url.startswith("postgresql://") and not db_url.startswith("postgresql+psycopg://"):
        db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
