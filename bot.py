# bot.py
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from config   import BOT_TOKEN
from database import add_pick, set_result, get_pending, get_picks_by_user
from utils    import calculate_stats


# ───────────────────────── Handlers ───────────────────────── #

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 Welcome!\n"
        "• /addpick <user> <odds> <stake>\n"
        "• /setresult <id> <win/loss>\n"
        "• /pending — unresolved bets\n"
        "• /stats <user>  → dashboard (today / week / month)\n"
        "• /stats <user> daily|weekly|monthly  → single period"
    )


async def addpick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user, odds, stake = context.args
        add_pick(user.strip(), float(odds), float(stake))
        await update.message.reply_text(f"✅ Pick added for {user}, awaiting result.")
    except Exception:
        await update.message.reply_text("❗ Usage: /addpick <user> <odds> <stake>")


async def setresult(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pick_id, result = context.args
        if result.lower() not in ("win", "loss"):
            raise ValueError()
        if set_result(pick_id, result.lower()):
            await update.message.reply_text("✅ Result updated.")
        else:
            await update.message.reply_text("❗ Pick not found.")
    except Exception:
        await update.message.reply_text("❗ Usage: /setresult <id> <win/loss>")


async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg_lines = []
    for doc in get_pending():
        short_id = doc.get("short_id", str(doc["_id"])[:6])
        msg_lines.append(
            f"{short_id} | {doc['user']} | Odds: {doc['odds']} | Stake: {doc['stake']}"
        )

    if msg_lines:
        await update.message.reply_text(
            "🕒 Pending Picks:\n" + "\n".join(msg_lines),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text("🎯 No pending picks.")


# --------- new, richer /stats command --------- #
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❗ Usage: /stats <user> [daily|weekly|monthly]")
        return

    user   = context.args[0]
    period = context.args[1].lower() if len(context.args) > 1 else None

    # helper – returns the ready-made line for a given period key
    def build_line(key: str, nice_name: str) -> str:
        picks = list(get_picks_by_user(user, key))
        if not picks:
            return f"➤ {nice_name}: —"      # em-dash if no finished picks

        st        = calculate_stats(picks)
        profit    = f"{st['profit']:+.0f}"   # +100 / -50
        ev_value  = st.get("ev", st.get("roi", 0))
        ev        = f"{ev_value:+.1f}%"
        return f"➤ {nice_name}: {profit} | {st['count']} Picks | EV: {ev}"

    # 1) user explicitly asked for a single period
    if period in ("daily", "weekly", "monthly"):
        mapping = {"daily": "Today", "weekly": "This Week", "monthly": "This Month"}
        await update.message.reply_text(build_line(period, mapping[period]))
        return

    # 2) default dashboard: show all three
    lines = [
        build_line("daily",   "Today"),
        build_line("weekly",  "This Week"),
        build_line("monthly", "This Month")
    ]
    await update.message.reply_text("\n".join(lines))


# ───────────────────────── Bot setup ───────────────────────── #

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start",      start))
app.add_handler(CommandHandler("addpick",    addpick))
app.add_handler(CommandHandler("setresult",  setresult))
app.add_handler(CommandHandler("pending",    pending))
app.add_handler(CommandHandler("stats",      stats))

app.run_polling()
