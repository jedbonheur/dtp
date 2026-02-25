from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db import engine, Base, get_db


app = FastAPI(title="tracking-service", version="0.1.0")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    # This demonstrates database connection with a session
    try:
        db.execute(text("SELECT 1"))
        return {"status": "i am alive", "database": "connected"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database not available")