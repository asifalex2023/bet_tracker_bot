# bot.py
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from config   import BOT_TOKEN, ADMIN_IDS
from database import (
    add_pick, set_result, get_pending,
    get_picks_by_user, get_all_users, reset_database
)
from utils    import calculate_stats


# ────────── helper functions ──────────
def dash_line(label: str, stats: dict) -> str:
    """One nicely formatted line for the /stats dashboard."""
    profit = f"{stats['profit']:+.0f}"
    roi    = f"{stats['ev']:+.1f}%"
    return f"➤ {label}: {profit} | {stats['count']} picks | 📈 {roi}"


def period_key_to_label(key: str) -> str:
    return {"daily": "Today", "weekly": "This Week", "monthly": "This Month"}[key]

# ───────────── /start ─────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 *Welcome to the Betting Tracker Bot!*\n"
        "Created with ❤️ by @asifalex\n\n"
        "Type /commands to see everything I can do.",
        parse_mode=ParseMode.MARKDOWN
    )


# ───────────── /commands (new) ─────────────
async def commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Command list*\n"
        "• `/addpick <user> <odds> <stake>` – add a new pick\n"
        "• `/setresult <id> <win/loss>` – close a pick\n"
        "• `/pending` – show all open bets\n"
        "• `/stats <user|all> (daily|weekly|monthly)` – performance stats\n"
        "• `/leaderboard (daily|weekly|monthly)` – top bettors\n"
        "• `/resetdb` – wipe database (admin only)",
        parse_mode=ParseMode.MARKDOWN
    )

# ───────────── /addpick (🎲 removed) ─────────────
async def addpick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user, odds, stake = context.args
        add_pick(user.strip(), float(odds), float(stake))
        await update.message.reply_text(
            f"🎯 New pick saved!\n"
            f"👤 *{user}* | Odds *{odds}* | 💵 *{stake}*",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        await update.message.reply_text("⚠️ Usage: /addpick <user> <odds> <stake>")


        
async def setresult(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pick_id, result = context.args
        if result.lower() not in ("win", "loss"):
            raise ValueError()
        if set_result(pick_id, result.lower()):
            await update.message.reply_text(
                "✅ Result stored." if result.lower() == "win" else "❌ Result stored."
            )
        else:
            await update.message.reply_text("🔎 Pick not found.")
    except Exception:
        await update.message.reply_text("⚠️ Usage: /setresult <id> <win/loss>")

# ───────────── /pending (🎲 removed) ─────────────
async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = [
        f"🆔 *{doc['short_id']}* | 👤 *{doc['user']}* | Odds {doc['odds']} | 💵 {doc['stake']}"
        for doc in get_pending()
    ]
    text = "⏳ *Pending Picks*\n" + ("\n".join(rows) if rows else "— none —")
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ---------- /stats ----------
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: /stats <user|all> [daily|weekly|monthly]"
        )
        return

    target = context.args[0].lower()
    period = context.args[1].lower() if len(context.args) > 1 else None

    def stats_for(user, p_key):
        return calculate_stats(list(get_picks_by_user(user, p_key)))

    # single-period request -------------------------------------------------
    if period in ("daily", "weekly", "monthly"):
        if target == "all":
            lines = [
                f"👤 *{user}*\n{dash_line(period_key_to_label(period), stats_for(user, period))}"
                for user in get_all_users()
            ]
            await update.message.reply_text(
                "\n\n".join(lines) if lines else "📉 No finished picks yet.",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            st = stats_for(target, period)
            await update.message.reply_text(
                f"📊 Stats for *{target}* ({period_key_to_label(period)}):\n"
                f"{dash_line(period_key_to_label(period), st)}",
                parse_mode=ParseMode.MARKDOWN
            )
        return

    # dashboard (today / week / month) --------------------------------------
    keys = ("daily", "weekly", "monthly")
    if target == "all":
        users_block = []
        for user in get_all_users():
            block_lines = [
                dash_line(period_key_to_label(k), stats_for(user, k)) for k in keys
            ]
            users_block.append(f"👤 *{user}*\n" + "\n".join(block_lines))
        await update.message.reply_text(
            "\n\n".join(users_block) if users_block else "📉 No finished picks yet.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        user_lines = [
            dash_line(period_key_to_label(k), stats_for(target, k)) for k in keys
        ]
        await update.message.reply_text(
            "\n".join(user_lines), parse_mode=ParseMode.MARKDOWN
        )

# ───────────── /leaderboard (🎲 removed, numbered) ─────────────
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    period = (context.args[0].lower() if context.args else "weekly")
    if period not in ("daily", "weekly", "monthly"):
        await update.message.reply_text("⚠️ Usage: /leaderboard [daily|weekly|monthly]")
        return

    board = []
    for user in get_all_users():
        s = calculate_stats(list(get_picks_by_user(user, period)))
        board.append((user, s["profit"], s["ev"], s["count"]))
    board.sort(key=lambda x: x[1], reverse=True)

    if not board:
        await update.message.reply_text("📉 No finished picks yet.")
        return

    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines  = []
    for idx, (user, profit, roi, cnt) in enumerate(board[:10], start=1):
        medal = medals[idx - 1] if idx <= len(medals) else "•"
        lines.append(
            f"{idx}. {medal} *{user}* | 💰 {profit:+.0f} | 📈 {roi:+.1f}% | {cnt} picks"
        )

    await update.message.reply_text(
        f"🏆 *Leaderboard* – {period_key_to_label(period)}\n" + "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN
    )


# ---------- /resetdb ----------
async def resetdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🚫 You’re not allowed to do that.")
        return
    reset_database()
    await update.message.reply_text("🗑️ Database wiped clean.")

# ───────────── bot init (add /commands handler) ─────────────
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start",       start))
app.add_handler(CommandHandler("commands",    commands))     # ← NEW
app.add_handler(CommandHandler("addpick",     addpick))
app.add_handler(CommandHandler("setresult",   setresult))
app.add_handler(CommandHandler("pending",     pending))
app.add_handler(CommandHandler("stats",       stats))
app.add_handler(CommandHandler("leaderboard", leaderboard))
app.add_handler(CommandHandler("resetdb",     resetdb))

app.run_polling()