from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from config import BOT_TOKEN
from database import add_pick, set_result, get_pending, get_picks_by_user
from utils import calculate_stats
from bson.objectid import ObjectId

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 Welcome! Use /addpick <user> <odds> <stake> to add a bet.\n"
        "Use /setresult <id> <win/loss> to finalize a pick.\n"
        "Use /pending to see unresolved bets.\n"
        "Use /stats <user> [daily|weekly|monthly] to view stats."
    )

async def addpick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user, odds, stake = context.args
        add_pick(user.strip(), float(odds), float(stake))
        await update.message.reply_text(f"✅ Pick added for {user}, awaiting result.")
    except Exception as e:
        await update.message.reply_text("❗ Usage: /addpick <user> <odds> <stake>")

async def setresult(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pick_id, result = context.args
        if result.lower() not in ["win", "loss"]:
            raise ValueError()
        set_result(pick_id, result.lower())
        await update.message.reply_text("✅ Result updated.")
    except:
        await update.message.reply_text("❗ Usage: /setresult <id> <win/loss>")

async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    picks = get_pending()
    msg_lines = []
    for doc in picks:
        short_id = str(doc['_id'])[:6]
        msg_lines.append(f"{short_id} | {doc['user']} | Odds: {doc['odds']} | Stake: {doc['stake']}")
    if not msg_lines:
        await update.message.reply_text("🎯 No pending picks.")
    else:
        await update.message.reply_text("🕒 Pending Picks:\n" + "\n".join(msg_lines))

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = context.args[0]
        period = context.args[1] if len(context.args) > 1 else "daily"
    except:
        await update.message.reply_text("❗ Usage: /stats <user> [daily|weekly|monthly]")
        return

    picks = list(get_picks_by_user(user, period))
    if not picks:
        await update.message.reply_text(f"📉 No completed picks found for {user}.")
        return

    stats = calculate_stats(picks)
    msg = (
        f"📊 Stats for {user} ({period}):\n"
        f"📈 Picks: {stats['count']}\n"
        f"💸 Profit: {stats['profit']}\n"
        f"📊 ROI: {stats['roi']}%\n"
        f"🎯 Hit Rate: {stats['hit_rate']}%"
    )
    await update.message.reply_text(msg)

app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addpick", addpick))
app.add_handler(CommandHandler("setresult", setresult))
app.add_handler(CommandHandler("pending", pending))
app.add_handler(CommandHandler("stats", stats))

app.run_polling()
