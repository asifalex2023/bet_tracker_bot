from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from config   import BOT_TOKEN, ADMIN_IDS
from database import (add_pick, set_result, get_pending,
                      get_picks_by_user, get_all_users, reset_database)
from utils    import calculate_stats

# ───────────────── helpers ───────────────── #
def dash_line(name: str, stats: dict) -> str:
    prof = f"{stats['profit']:+.0f}"
    ev   = f"{stats['ev']:+.1f}%"
    return f"➤ {name}: {prof} | {stats['count']} picks | EV: {ev}"

def period_key_to_label(key: str) -> str:
    return {"daily": "Today", "weekly": "This Week", "monthly": "This Month"}[key]

# ───────────────── handlers ───────────────── #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Welcome!\n"
        "• /addpick <user> <odds> <stake>\n"
        "• /setresult <id> <win/loss>\n"
        "• /pending – show open bets\n"
        "• /stats <user|all> [daily|weekly|monthly]\n"
        "• /leaderboard [daily|weekly|monthly]\n"
        "• /resetdb – admin only",
        parse_mode=ParseMode.MARKDOWN
    )

# bot.py  (only the handlers shown were changed)  ────────────────────
async def addpick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user, odds, stake = context.args
        add_pick(user.strip(), float(odds), float(stake))
        await update.message.reply_text(
            f"🎯 New pick saved!\n👤 *{user}*  |  🎲 *{odds}*  |  💵 *{stake}*",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        await update.message.reply_text("⚠️ Usage: /addpick <user> <odds> <stake>")

async def setresult(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pick_id, result = context.args
        if result.lower() not in ("win", "loss"):
            raise ValueError()
        if set_result(pick_id, result.lower()):
            emoji = "✅" if result.lower() == "win" else "❌"
            await update.message.reply_text(f"{emoji} Result stored.")
        else:
            await update.message.reply_text("🔎 Pick not found.")
    except Exception:
        await update.message.reply_text("⚠️ Usage: /setresult <id> <win/loss>")

async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = []
    for doc in get_pending():
        rows.append(
            f"🆔 *{doc['short_id']}*  |  👤 *{doc['user']}*  |  🎲 {doc['odds']}  |  💵 {doc['stake']}"
        )
    text = "⏳ *Pending Picks*\n" + ("\n".join(rows) if rows else "— none —")
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    period = (context.args[0].lower() if context.args else "weekly")
    if period not in ("daily", "weekly", "monthly"):
        await update.message.reply_text("⚠️ Usage: /leaderboard [daily|weekly|monthly]")
        return

    board = []
    for u in get_all_users():
        s = calculate_stats(list(get_picks_by_user(u, period)))
        board.append((u, s["profit"], s["ev"], s["count"]))
    board.sort(key=lambda x: x[1], reverse=True)

    if not board:
        await update.message.reply_text("📉 No finished picks yet.")
        return

    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = [
        f"{medals[i] if i < len(medals) else '•'}  👤 *{u}*  {p:+.0f}  (EV {ev:+.1f}%, {c} picks)"
        for i, (u, p, ev, c) in enumerate(board[:10])
    ]
    await update.message.reply_text(
        f"🏆 *Leaderboard* – {period.capitalize()}\n" + "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )

async def setresult(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pick_id, result = context.args
        if result.lower() not in ("win", "loss"):
            raise ValueError()
        if set_result(pick_id, result.lower()):
            await update.message.reply_text("🎉 Result updated.")
        else:
            await update.message.reply_text("❌ Pick not found.")
    except Exception:
        await update.message.reply_text("⚠️ Usage: /setresult <id> <win/loss>")

async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = [
        f"{doc.get('short_id', str(doc['_id'])[:6])} | {doc['user']} | "
        f"Odds {doc['odds']} | Stake {doc['stake']}"
        for doc in get_pending()
    ]
    await update.message.reply_text(
        "⏳ *Pending Picks:*\n" + ("\n".join(lines) if lines else "— None —"),
        parse_mode=ParseMode.MARKDOWN
    )

# -------- STATS -------- #
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /stats <user|all> [daily|weekly|monthly]")
        return

    target = context.args[0].lower()
    period = context.args[1].lower() if len(context.args) > 1 else None

    def stats_for(user, period_key):
        return calculate_stats(list(get_picks_by_user(user, period_key)))

    # 1) /stats <user> daily|weekly|monthly
    if period in ("daily", "weekly", "monthly"):
        if target == "all":
            reply = []
            for u in get_all_users():
                s = stats_for(u, period)
                reply.append(f"👤 *u/{u}*\n{dash_line(period_key_to_label(period), s)}")
            await update.message.reply_text("\n\n".join(reply), parse_mode=ParseMode.MARKDOWN)
        else:
            st = stats_for(target, period)
            await update.message.reply_text(
                f"📊 Stats for *{target}* ({period_key_to_label(period)}):\n"
                f"{dash_line(period_key_to_label(period), st)}",
                parse_mode=ParseMode.MARKDOWN
            )
        return

    # 2) /stats <user|all>   → dashboard (today/week/month)
    keys = ("daily", "weekly", "monthly")
    if target == "all":
        big_reply = []
        for u in get_all_users():
            lines = [dash_line(period_key_to_label(k), stats_for(u, k)) for k in keys]
            big_reply.append(f"👤 *u/{u}*\n" + "\n".join(lines))
        await update.message.reply_text("\n\n".join(big_reply), parse_mode=ParseMode.MARKDOWN)
    else:
        lines = [dash_line(period_key_to_label(k), stats_for(target, k)) for k in keys]
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

# -------- LEADERBOARD -------- #
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    period = (context.args[0].lower() if context.args else "weekly")
    if period not in ("daily", "weekly", "monthly"):
        await update.message.reply_text("⚠️ Usage: /leaderboard [daily|weekly|monthly]")
        return
    board = []
    for u in get_all_users():
        st = calculate_stats(list(get_picks_by_user(u, period)))
        board.append((u, st["profit"], st["ev"], st["count"]))
    # sort by profit desc
    board.sort(key=lambda x: x[1], reverse=True)
    medals = ["🥇","🥈","🥉"] + ["🏅"]*7
    lines  = [
        f"{medals[i] if i < len(medals) else '•'} *u/{u}*  {profit:+.0f}  (EV {ev:+.1f}%, {cnt} picks)"
        for i,(u,profit,ev,cnt) in enumerate(board[:10])
    ]
    await update.message.reply_text(
        f"🏆 *Leaderboard* – {period_key_to_label(period)}\n" + "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN
    )

# -------- RESET DB -------- #
async def resetdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🚫 You’re not allowed to do that.")
        return
    reset_database()
    await update.message.reply_text("🗑️ Database wiped clean.")

# ───────────────── bot init ───────────────── #
app = ApplicationBuilder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start",       start))
app.add_handler(CommandHandler("addpick",     addpick))
app.add_handler(CommandHandler("setresult",   setresult))
app.add_handler(CommandHandler("pending",     pending))
app.add_handler(CommandHandler("stats",       stats))
app.add_handler(CommandHandler("leaderboard", leaderboard))
app.add_handler(CommandHandler("resetdb",     resetdb))

app.run_polling()
