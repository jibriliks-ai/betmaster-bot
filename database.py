import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import date

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# If no Postgres URL, use SQLite file (bot will still work!)
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./betmaster.db"
    print("WARNING: No DATABASE_URL - using SQLite fallback")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, default="")
    is_vip = Column(Boolean, default=False)
    vip_expiry = Column(Date, nullable=True)
    daily_count = Column(Integer, default=0)
    last_date = Column(Date, default=date.today)

Base.metadata.create_all(bind=engine)

def get_user(db, telegram_id: int):
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        user = User(telegram_id=telegram_id, daily_count=0, last_date=date.today())
        db.add(user)
        db.commit()
        db.refresh(user)
    if user.last_date != date.today():
        user.daily_count = 0
        user.last_date = date.today()
        db.commit()
    return user
