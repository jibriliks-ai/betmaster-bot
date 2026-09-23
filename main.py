import os, asyncio, pathlib
from datetime import date, datetime, timedelta
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from database import SessionLocal, get_user
from fetcher import get_todays_fixtures, get_odds_from_api_football
from predictor import get_ai_prediction
import uvicorn, requests

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_USERNAME = os.getenv("GROUP_USERNAME", "@betmasterpro")
PAYSTACK_LINK = os.getenv("PAYSTACK_LINK", "/subscribe")
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET", "")
WEBSITE_URL = os.getenv("WEBSITE_URL", "")

# Safe ADMIN_ID parsing - no crash
try:
    ADMIN_ID = int(str(os.getenv("ADMIN_ID","0")).strip().split()[0])
except:
    ADMIN_ID = 0

app = FastAPI()
telegram_app = Application.builder().token(BOT_TOKEN).build() if BOT_TOKEN else None
FREE_LIMIT=2; VIP_LIMIT=10

def check_limit(user):
    limit = VIP_LIMIT if getattr(user, 'is_vip', False) else FREE_LIMIT
    return user.daily_count < limit, limit

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db=SessionLocal(); user=get_user(db, update.effective_user.id); user.username=update.effective_user.username or ""; db.commit()
    sub_url=(WEBSITE_URL+"/subscribe") if WEBSITE_URL else PAYSTACK_LINK
    keyboard=[[InlineKeyboardButton("Join @betmasterpro", url=f"https://t.me/{GROUP_USERNAME.replace('@','')}")],[InlineKeyboardButton("Subscribe N2000", url=sub_url)]]
    limit=VIP_LIMIT if getattr(user,'is_vip',False) else FREE_LIMIT
    await update.message.reply_text(f"Welcome! FREE {FREE_LIMIT}/day VIP {VIP_LIMIT}/day Type: Arsenal vs Chelsea\nYou: {user.daily_count}/{limit}", reply_markup=InlineKeyboardMarkup(keyboard))
    db.close()

async def predict_any_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type!="private": return
    text=(update.message.text or "").strip()
    if len(text)<4 or text.startswith("/") or "http" in text.lower(): return
    db=SessionLocal(); user=get_user(db, update.effective_user.id)
    can_predict,limit=check_limit(user)
    if not can_predict:
        sub_url=(WEBSITE_URL+"/subscribe") if WEBSITE_URL else PAYSTACK_LINK
        await update.message.reply_text(f"Limit {limit}/{limit} Join {GROUP_USERNAME}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Subscribe", url=sub_url)]])); db.close(); return
    await update.message.reply_text(f"Analyzing {text}...")
    home,away=(text.split("vs")[0].strip().title(), text.split("vs")[1].strip().title()) if "vs" in text.lower() else (text.title(),"Away")
    data={"home":home,"away":away,"league":"Custom","home_xg":1.5,"away_xg":1.2,"home_form":"WDWWL","away_form":"LWDWL","h2h":2,"home_inj":"None","away_inj":"None","odds_h":2.1,"odds_d":3.2,"odds_a":3.4,"odds_over":1.75}
    pred=get_ai_prediction(data); user.daily_count+=1; db.commit()
    await update.message.reply_text(f"⚽ {home} vs {away}\nPick: {pred['best_pick']} {pred['confidence']}\n{pred['explanation']}\nLeft {limit-user.daily_count}/{limit}"); db.close()

@app.get("/subscribe", response_class=HTMLResponse)
async def subscribe_page():
    p=pathlib.Path("static/index.html")
    if not p.exists(): return HTMLResponse("<h1>BetMaster</h1><p>Create static/index.html</p>")
    html=p.read_text(encoding="utf-8").replace("{{PUBLIC_KEY}}", PAYSTACK_PUBLIC_KEY or "").replace("{{GROUP_USERNAME}}", GROUP_USERNAME)
    return HTMLResponse(html)

@app.get("/api/verify/{reference}")
async def verify_pay(reference: str, tg_id: int, plan: str):
    if not PAYSTACK_SECRET: return {"status":"failed","error":"No secret"}
    r=requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers={"Authorization": f"Bearer {PAYSTACK_SECRET}"}, timeout=15).json()
    if r.get('data',{}).get('status')=='success':
        days=7 if plan=='weekly' else 30; db=SessionLocal(); user=get_user(db,tg_id); user.is_vip=True; user.vip_expiry=date.today()+timedelta(days=days); db.commit(); db.close()
        if telegram_app:
            try: await telegram_app.bot.send_message(chat_id=tg_id, text=f"VIP active {days} days")
            except: pass
        return {"status":"success","days":days}
    return {"status":"failed"}

@app.get("/")
async def home(): return {"status":"live","has_openrouter":bool(os.getenv("OPENROUTER_KEY")),"has_bot_token":bool(BOT_TOKEN),"admin_id":ADMIN_ID}

if telegram_app:
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, predict_any_text))

async def run_bot():
    if not telegram_app: return
    await telegram_app.initialize(); await telegram_app.start(); await telegram_app.updater.start_polling()

if __name__=="__main__":
    import threading; loop=asyncio.new_event_loop()
    def start_loop():
        asyncio.set_event_loop(loop); loop.run_until_complete(run_bot()); loop.run_forever()


    try:
    ADMIN_ID = int(str(os.getenv("ADMIN_ID","0")).strip().split()[0])
except:
    ADMIN_ID = 0
    threading.Thread(target=start_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT",10000)))
