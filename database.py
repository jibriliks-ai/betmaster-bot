from sqlalchemy import create_engine, Column, Integer, String, Boolean, Date
from sqlalchemy.orm import declarative_base, sessionmaker
import os
from datetime import date
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL) if DATABASE_URL else create_engine("sqlite:///./betmaster.db")
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True) # telegram id
    username = Column(String(100))
    is_vip = Column(Boolean, default=False)
    vip_expiry = Column(Date, nullable=True)
    daily_count = Column(Integer, default=0)
    last_reset = Column(Date, default=date.today)

Base.metadata.create_all(bind=engine)

def get_user(db, tg_id):
    user = db.query(User).filter(User.id == tg_id).first()
    if not user:
        user = User(id=tg_id, last_reset=date.today())
        db.add(user)
        db.commit()
        db.refresh(user)
    if user.last_reset != date.today():
        user.daily_count = 0
        user.last_reset = date.today()
        db.commit()
    if user.is_vip and user.vip_expiry and user.vip_expiry < date.today():
        user.is_vip = False
        db.commit()
    return user
