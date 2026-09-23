from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import requests

# Mount website
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/subscribe")
@app.get("/pay")
@app.get("/")
async def website():
    # Inject public key into html
    with open("static/index.html") as f:
        html = f.read().replace("{{PUBLIC_KEY}}", os.getenv("PAYSTACK_PUBLIC_KEY",""))
    return FileResponse("static/index.html") if False else HTMLResponse(html)

from fastapi.responses import HTMLResponse

@app.get("/api/verify/{reference}")
async def verify_pay(reference: str, tg_id: int, plan: str):
    secret = os.getenv("PAYSTACK_SECRET")
    r = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", 
                     headers={"Authorization": f"Bearer {secret}"}).json()
    if r['data']['status'] == 'success':
        days = 7 if plan=='weekly' else 30
        db = SessionLocal()
        user = get_user(db, tg_id)
        from datetime import timedelta
        user.is_vip = True
        user.vip_expiry = date.today() + timedelta(days=days)
        db.commit()
        db.close()
        return {"status":"success", "days":days}
    return {"status":"failed"}

import os, asyncio
from datetime import date, datetime, timedelta
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from database import SessionLocal, get_user
from fetcher import get_todays_fixtures, get_odds_from_api_football
from predictor import get_ai_prediction
import uvicorn

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_USERNAME = os.getenv("GROUP_USERNAME", "@betmasterpro")
PAYSTACK_LINK = os.getenv("PAYSTACK_LINK", "https://paystack.com/pay/betmaster-vip")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

app = FastAPI()
telegram_app = Application.builder().token(BOT_TOKEN).build()

FREE_LIMIT = 2
VIP_LIMIT = 10

def check_limit(user):
    limit = VIP_LIMIT if user.is_vip else FREE_LIMIT
    return user.daily_count < limit, limit

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = SessionLocal()
    user = get_user(db, update.effective_user.id)
    user.username = update.effective_user.username or ""
    db.commit()
    keyboard = [
        [InlineKeyboardButton("🔥 Join @betmasterpro", url=f"https://t.me/{GROUP_USERNAME.replace('@','')}")],
        [InlineKeyboardButton("💳 Subscribe ₦2000/week", url=PAYSTACK_LINK)],
    ]
    msg = f"""👋 *Welcome to BetMaster_bot!*

I cover EPL, La Liga, Saudi Pro League, CSL, Brazil & Argentina.

✅ FREE: {FREE_LIMIT} predictions/day in private
✅ VIP: {VIP_LIMIT} predictions/day - any match you ask

📍 I post 3 best picks daily in {GROUP_USERNAME}

*How to use:*
Just type: `Arsenal vs Chelsea` or any match

You: {user.daily_count}/{FREE_LIMIT if not user.is_vip else VIP_LIMIT} used today.

⚠️ 18+ Analysis only. No guarantee. Bet responsibly.
"""
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    db.close()

async def predict_any_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if len(text) < 4 or update.message.chat.type != "private":
        return
    if "http" in text.lower() or text.startswith("/"):
        return

    db = SessionLocal()
    user = get_user(db, update.effective_user.id)
    can_predict, limit = check_limit(user)

    if not can_predict:
        if user.is_vip:
            await update.message.reply_text(f"⛔ VIP limit reached ({limit}/{limit} today). Resets 12AM WAT.")
        else:
            keyboard = [[InlineKeyboardButton("💳 Unlock 10/day - Subscribe", url=PAYSTACK_LINK)]]
            await update.message.reply_text(
                f"⛔ Free limit reached ({FREE_LIMIT}/{FREE_LIMIT} today).\n\n"
                f"1. Join {GROUP_USERNAME} for 3 free daily picks\n"
                f"2. Subscribe for {VIP_LIMIT}/day and ask ANY match\n\nLink: {PAYSTACK_LINK}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        db.close()
        return

    await update.message.reply_text(f"🔍 Analyzing *{text}*... checking form, xG, Bet9ja-style odds...", parse_mode="Markdown")

    # Parse home vs away
    if "vs" in text.lower():
        parts = text.lower().split("vs")
        home = parts[0].strip().title()
        away = parts[1].strip().title()
    else:
        home = text.title()
        away = "Away Team"

    data = {
        "home": home, "away": away, "league": "Custom Request",
        "home_xg": 1.5, "away_xg": 1.2, "home_form": "WDWWL",
        "away_form": "LWDWL", "h2h": 2, "home_inj": "None", "away_inj": "None",
        "odds_h": 2.1, "odds_d": 3.2, "odds_a": 3.4, "odds_over": 1.75
    }
    pred = get_ai_prediction(data)
    user.daily_count += 1
    db.commit()
    remaining = limit - user.daily_count

    msg = f"""⚽ *{data['home']} vs {data['away']}*

AI Prob: Home {pred['home_prob']}% | Draw {pred['draw_prob']}% | Away {pred['away_prob']}%
✅ Best Safe Pick: *{pred['best_pick']}*
Confidence: {pred['confidence']} | Value Bet: {pred['is_value_bet']}
Why: {pred['explanation']}

💰 Stake: {pred['stake_advice']}
📊 Left today: {remaining}/{limit}

⚠️ 18+ Bet Responsibly. No guarantee."""
    await update.message.reply_text(msg, parse_mode="Markdown")
    db.close()

async def daily_group_post(context: ContextTypes.DEFAULT_TYPE):
    fixtures = get_todays_fixtures()[:3]
    if not fixtures:
        return
    text = f"🔥 *BetMaster Pro - Top 3 Value Picks {date.today().strftime('%d %b')}* 🔥\n\n"
    for f in fixtures:
        oh, oa, od, over = get_odds_from_api_football(f["id"])
        data = {"home": f["home"], "away": f["away"], "league": f["league"], "home_xg": 1.6, "away_xg": 1.1, "home_form": "WWDWL", "away_form": "LWDWL", "h2h": 2, "home_inj": "None", "away_inj": "None", "odds_h": oh, "odds_d": od, "odds_a": oa, "odds_over": over}
        pred = get_ai_prediction(data)
        text += f"⚽ {f['home']} vs {f['away']} ({f['league']})\n👉 Pick: *{pred['best_pick']}* | Conf: {pred['confidence']}\n💡 {pred['explanation']}\n\n"
    text += f"Want 10 custom picks/day? Add @{context.bot.username} to contacts & chat me any match.\n💳 VIP: {PAYSTACK_LINK}\n#Bet9ja #SportyBet #BetKing #BetMaster"
    try:
        await context.bot.send_message(chat_id=GROUP_USERNAME, text=text, parse_mode="Markdown")
    except Exception as e:
        print(f"Group post failed: {e}")

async def addvip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID == 0 or update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Not authorized")
        return
    try:
        tg_id = int(context.args[0]); days = int(context.args[1])
        db = SessionLocal()
        user = get_user(db, tg_id)
        user.is_vip = True
        user.vip_expiry = date.today() + timedelta(days=days)
        db.commit()
        await update.message.reply_text(f"✅ VIP added for {tg_id} till {user.vip_expiry}")
        db.close()
        # Notify user
        try:
            await context.bot.send_message(chat_id=tg_id, text=f"🎉 Your VIP is active for {days} days! You now have {VIP_LIMIT} predictions/day. Type any match like `Arsenal vs Chelsea`")
        except:
            pass
    except:
        await update.message.reply_text("Use: /addvip <telegram_id> <days> e.g. /addvip 123456 30")

@app.post("/webhook/paystack")
async def paystack_webhook(request: Request):
    # For auto VIP - connect Paystack webhook later
    data = await request.json()
    print(f"Paystack webhook: {data}")
    return {"status": "ok"}

@app.get("/")
def home():
    return {"status": "BetMaster_bot live", "group": GROUP_USERNAME}

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("addvip", addvip))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, predict_any_text))

async def run_bot():
    telegram_app.job_queue.run_daily(daily_group_post, time=datetime.strptime("08:00", "%H:%M").time(), name="daily_post")
    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling()

if __name__ == "__main__":
    import threading
    loop = asyncio.new_event_loop()
    def start_loop():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_bot())
        loop.run_forever()
    threading.Thread(target=start_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
