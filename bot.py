# bot.py
from functools             import wraps
from telegram               import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants     import ParseMode
from telegram.ext           import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
)

from config   import BOT_TOKEN, ADMIN_IDS
from database import (
    add_pick, set_result, get_pending,
    get_picks_by_user, get_all_users, reset_database
)
from utils    import calculate_stats


# ────────── helper functions ──────────
def dash_line(label: str, stats: dict) -> str:
    profit = f"{stats['profit']:+.0f}"
    roi    = f"{stats['ev']:+.1f}%"
    return f"➤ {label}: {profit} | {stats['count']} picks | 📈 {roi}"


def period_key_to_label(key: str) -> str:
    return {"daily": "Today", "weekly": "This Week", "monthly": "This Month"}[key]


# ───────────── admin guard ─────────────
def admin_required(handler):
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text(
                "🚫 *Sorry, this bot can only be used by @asifalex.*",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        return await handler(update, context, *args, **kwargs)
    return wrapper


# ───────────── /start ─────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 *Welcome to the Betting Tracker Bot!*\n"
        "Created with ❤️ by @asifalex\n\n"
        "Type /commands to see everything I can do.",
        parse_mode=ParseMode.MARKDOWN
    )


# ───────────── /commands ─────────────
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


# ───────────── protected commands ─────────────
@admin_required
async def addpick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user, odds, stake = context.args
        add_pick(user.strip(), float(odds), float(stake))
        await update.message.reply_text(
            f"🎯 New pick saved!\n👤 *{user}* | Odds *{odds}* | 💵 *{stake}*",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        await update.message.reply_text("⚠️ Usage: /addpick <user> <odds> <stake>")


@admin_required
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


@admin_required
async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = [
        f"🆔 *{doc['short_id']}* | 👤 *{doc['user']}* | Odds {doc['odds']} | 💵 {doc['stake']}"
        for doc in get_pending()
    ]
    txt = "⏳ *Pending Picks*\n" + ("\n".join(rows) if rows else "— none —")
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)


@admin_required
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # … (unchanged code) …
    # keep the body exactly as you have it
    # -------------------------------------------------------------
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: /stats <user|all> [daily|weekly|monthly]"
        )
        return
    target = context.args[0].lower()
    period = context.args[1].lower() if len(context.args) > 1 else None

    def stats_for(user, p_key):
        return calculate_stats(list(get_picks_by_user(user, p_key)))

    if period in ("daily", "weekly", "monthly"):
        if target == "all":
            lines = [
                f"👤 *{user}*\n{dash_line(period_key_to_label(period), stats_for(user, period))}"
                for user in get_all_users()
            ]
            await update.message.reply_text(
                "\n\n".join(lines) if lines else "📉 No finished picks yet.",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            st = stats_for(target, period)
            await update.message.reply_text(
                f"📊 Stats for *{target}* ({period_key_to_label(period)}):\n"
                f"{dash_line(period_key_to_label(period), st)}",
                parse_mode=ParseMode.MARKDOWN,
            )
        return

    keys = ("daily", "weekly", "monthly")
    if target == "all":
        users_block = []
        for user in get_all_users():
            block = [
                dash_line(period_key_to_label(k), stats_for(user, k)) for k in keys
            ]
            users_block.append(f"👤 *{user}*\n" + "\n".join(block))
        await update.message.reply_text(
            "\n\n".join(users_block) if users_block else "📉 No finished picks yet.",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        user_lines = [
            dash_line(period_key_to_label(k), stats_for(target, k)) for k in keys
        ]
        await update.message.reply_text(
            "\n".join(user_lines), parse_mode=ParseMode.MARKDOWN
        )


@admin_required
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # … body unchanged …
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


@admin_required
async def resetdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if context.args and context.args[0].lower() == "yes":
        reset_database()
        await update.message.reply_text("🗑️ Database wiped clean.")
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes — wipe it", callback_data="resetdb_yes"),
            InlineKeyboardButton("❌ No — keep data",  callback_data="resetdb_no"),
        ]
    ])
    await update.message.reply_text(
        "⚠️ *Danger!*  This will delete _every_ pick.\nAre you sure?",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


async def confirm_resetdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("🚫 No permission.")
        return
    if query.data == "resetdb_yes":
        reset_database()
        await query.edit_message_text("🗑️ Database wiped clean.")
    else:
        await query.edit_message_text("✅ Reset cancelled.")


# ───────────── bot init ─────────────
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start",       start))
app.add_handler(CommandHandler("commands",    commands))
app.add_handler(CommandHandler("addpick",     addpick))
app.add_handler(CommandHandler("setresult",   setresult))
app.add_handler(CommandHandler("pending",     pending))
app.add_handler(CommandHandler("stats",       stats))
app.add_handler(CommandHandler("leaderboard", leaderboard))
app.add_handler(CommandHandler("resetdb",     resetdb))
app.add_handler(CallbackQueryHandler(confirm_resetdb, pattern="^resetdb_"))

app.run_polling()
