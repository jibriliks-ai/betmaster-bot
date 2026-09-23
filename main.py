import os, asyncio
from datetime import date, datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from database import SessionLocal, get_user
from fetcher import get_todays_fixtures, get_odds_from_api_football
from predictor import get_ai_prediction
import uvicorn, requests

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_USERNAME = os.getenv("GROUP_USERNAME", "@betmasterpro")
PAYSTACK_LINK = os.getenv("PAYSTACK_LINK", "/subscribe")
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_SECRET = os.getenv("PAYSTACK_SECRET", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBSITE_URL = os.getenv("WEBSITE_URL", "") # e.g. https://betmaster-bot.onrender.com

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
    subscribe_url = WEBSITE_URL + "/subscribe" if WEBSITE_URL else PAYSTACK_LINK
    keyboard = [
        [InlineKeyboardButton("🔥 Join @betmasterpro", url=f"https://t.me/{GROUP_USERNAME.replace('@','')}")],
        [InlineKeyboardButton("💳 Subscribe on Website - N2000", url=subscribe_url)],
    ]
    limit = VIP_LIMIT if user.is_vip else FREE_LIMIT
    msg = f"""👋 *Welcome to BetMaster_bot!*

I cover EPL, La Liga, Saudi Pro League, CSL, Brazil & Argentina.

✅ FREE: {FREE_LIMIT} predictions/day in private
✅ VIP: {VIP_LIMIT} predictions/day - any match you ask

📍 I post 3 best picks daily in {GROUP_USERNAME}

*How to use:*
Just type: `Arsenal vs Chelsea` or any match

You: {user.daily_count}/{limit} used today.
Status: {"💎 VIP" if user.is_vip else "Free"} {f"till {user.vip_expiry}" if user.is_vip and user.vip_expiry else ""}

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
        subscribe_url = WEBSITE_URL + "/subscribe" if WEBSITE_URL else PAYSTACK_LINK
        if user.is_vip:
            await update.message.reply_text(f"⛔ VIP limit reached ({limit}/{limit} today). Resets 12AM WAT.")
        else:
            keyboard = [[InlineKeyboardButton("💳 Subscribe on Website - Unlock 10/day", url=subscribe_url)]]
            await update.message.reply_text(
                f"⛔ Free limit reached ({FREE_LIMIT}/{FREE_LIMIT} today).\n\n"
                f"1. Join {GROUP_USERNAME} for 3 free daily picks\n"
                f"2. Subscribe on website for {VIP_LIMIT}/day and ask ANY match\n\nWebsite: {subscribe_url}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        db.close()
        return

    await update.message.reply_text(f"🔍 Analyzing *{text}*... checking form, xG, Bet9ja-style odds...", parse_mode="Markdown")

    if "vs" in text.lower():
        parts = text.lower().split("vs")
        home = parts[0].strip().title()
        away = parts[1].strip().title()
    elif "-" in text:
        parts = text.split("-")
        home = parts[0].strip().title()
        away = parts[1].strip().title()
    else:
        home = text.title()
        away = "Away"

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
Confidence: {pred['confidence']} | Value: {pred['is_value_bet']}
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
    sub_url = WEBSITE_URL + "/subscribe" if WEBSITE_URL else PAYSTACK_LINK
    text += f"Want 10 custom picks/day? Add @{context.bot.username} to contacts & chat me any match.\n💳 Subscribe: {sub_url}\n#Bet9ja #SportyBet #BetMaster"
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
        try:
            await context.bot.send_message(chat_id=tg_id, text=f"🎉 Your VIP is active for {days} days! You now have {VIP_LIMIT} predictions/day. Type any match like `Arsenal vs Chelsea`")
        except:
            pass
    except Exception as e:
        await update.message.reply_text(f"Use: /addvip <telegram_id> <days> e.g. /addvip 123456 30\nError: {e}")

# Website routes
@app.get("/subscribe", response_class=HTMLResponse)
@app.get("/pay", response_class=HTMLResponse)
async def subscribe_page():
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            html = f.read()
        html = html.replace("{{PUBLIC_KEY}}", PAYSTACK_PUBLIC_KEY)
        html = html.replace("{{GROUP_USERNAME}}", GROUP_USERNAME)
        return HTMLResponse(html)
    except FileNotFoundError:
        return HTMLResponse("<h1>Upload static/index.html file</h1>")

@app.get("/api/verify/{reference}")
async def verify_pay(reference: str, tg_id: int, plan: str):
    if not PAYSTACK_SECRET:
        return {"status":"failed", "error":"No PAYSTACK_SECRET set"}
    try:
        r = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", 
                         headers={"Authorization": f"Bearer {PAYSTACK_SECRET}"}, timeout=15).json()
        if r.get('data',{}).get('status') == 'success':
            days = 7 if plan=='weekly' else 30
            db = SessionLocal()
            user = get_user(db, tg_id)
            user.is_vip = True
            user.vip_expiry = date.today() + timedelta(days=days)
            db.commit()
            db.close()
            # Notify user on telegram
            try:
                await telegram_app.bot.send_message(chat_id=tg_id, text=f"🎉 Payment confirmed! VIP active for {days} days ({plan}). You now have {VIP_LIMIT}/day. Type any match e.g. `Man City vs Arsenal`")
            except Exception as e:
                print(f"Notify fail: {e}")
            return {"status":"success", "days":days}
        return {"status":"failed", "data": r}
    except Exception as e:
        return {"status":"error", "error": str(e)}

@app.get("/")
async def home():
    return {"status": "BetMaster_bot live", "group": GROUP_USERNAME, "website": "/subscribe"}

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
