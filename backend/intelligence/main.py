from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from .database import get_db


app = FastAPI(
    title="GUDAKESA Intelligence API",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "message": "GUDAKESA Intelligence API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/db-test")
def database_test(db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT 1")
    )

    return {
        "database": "connected",
        "result": result.scalar(),
    }
