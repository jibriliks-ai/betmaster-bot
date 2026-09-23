# BetMaster_bot - 1-Click Deploy

Free: 2/day, VIP: 10/day. Auto posts 3 picks to @betmasterpro daily 9AM WAT.

1. Push this folder to GitHub
2. Go to Render.com > New > Blueprint > Connect this repo
3. Render reads render.yaml and creates bot + free postgres automatically
4. Add env vars in Render dashboard: BOT_TOKEN, API_FOOTBALL_KEY, OPENROUTER_KEY, ADMIN_ID
5. Make bot admin in @betmasterpro group
6. Done

Commands:
/start - welcome
Arsenal vs Chelsea - predict (just type)
/addvip <id> <days> - admin only

Paystack webhook: set webhook URL to https://your-app.onrender.com/webhook/paystack
