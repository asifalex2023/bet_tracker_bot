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
from datetime import datetime

# ────────── helpers ──────────
def money(val: float) -> str:
    """+123 → $+123, –45.5 → $-45.5 (no decimals if .0)."""
    whole = int(val)
    return f"${whole:+}" if val.is_integer() else f"${val:+.1f}"

def period_line(label: str, profit: float, picks: int, roi: float) -> str:
    """Return the ‘├─ Week: …’ style row used in the /stats all layout."""
    icon = "✅" if profit > 0 else "❌" if profit < 0 else "➖"
    return (
        f"├─ {label}: {money(profit)} | {picks} pick{'s' if picks != 1 else ''} | "
        f"{icon} {roi:+.1f}%"
    )

# NEW ↓↓↓ ──────────────────────────────────────────────────────────────
def dash_line(label: str, stats: dict) -> str:
    """
    Single-line summary used by:
      • /stats <user> daily|weekly|monthly
      • /stats all daily|weekly|monthly
    Example: ➤ Today: $+120 | 3 picks | 📈 +23.4%
    """
    return (
        f"➤ {label}: {money(stats['profit'])} | {stats['count']} pick"
        f"{'s' if stats['count'] != 1 else ''} | 📈 {stats['roi']:+.1f}%"
    )

def period_key_to_label(key: str) -> str:
    """Convert an internal period key to a human label."""
    return {"daily": "Today", "weekly": "This Week", "monthly": "This Month"}[key]
# ──────────────────────────────────────────────────────────────────────


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
    # ─────────── NEW ‘/stats all’ block ───────────
    if target == "all":
        # aggregate over *all* finished picks in the DB
        total_profit = total_stake = wins = losses = 0
        total_picks  = 0
        user_sections = []

        for user in get_all_users():
            # lifetime numbers for this user
            picks_life = list(get_picks_by_user(user, "lifetime"))
            if not picks_life:
                continue

            stats_life = calculate_stats(picks_life)
            profit_life = stats_life["profit"]
            ev_life     = stats_life["roi"]

            # daily / weekly / monthly
            p_today   = calculate_stats(list(get_picks_by_user(user, "daily")))
            p_week    = calculate_stats(list(get_picks_by_user(user, "weekly")))
            p_month   = calculate_stats(list(get_picks_by_user(user, "monthly")))

            # build the 4-row section for this user
            section = [
                f"**{user}** » {'📈' if profit_life>0 else '📉'} {money(profit_life)} (Lifetime)",
                period_line("Today",  p_today["profit"],  p_today["count"],  p_today["roi"]),
                period_line("Week",   p_week["profit"],   p_week["count"],   p_week["roi"]),
                period_line("Month",  p_month["profit"],  p_month["count"],  p_month["roi"]),
                f"└─ Lifetime: {money(profit_life)} | {stats_life['count']} pick{'s' if stats_life['count']!=1 else ''} | {ev_life:.2f} EV",
                ""
            ]
            user_sections.append("\n".join(section))

            # accumulate for group summary
            total_profit += profit_life
            total_stake  += sum(float(doc["stake"]) for doc in picks_life)
            wins         += sum(1 for doc in picks_life if doc["result"]=="win")
            losses       += sum(1 for doc in picks_life if doc["result"]=="loss")
            total_picks  += len(picks_life)

        win_rate = (wins / total_picks) * 100 if total_picks else 0
        avg_roi  = (total_profit / total_stake) * 100 if total_stake else 0

        msg = [
            "🔋 *EV TRACKER - COMPREHENSIVE STATS*",
            "/stats all",
            "",
            "*🏆 GROUP SUMMARY*",
            f"✅ **Net Profit**: {money(total_profit)}",
            f"📊 **Total Picks**: {total_picks}",
            f"📈 **Win Rate**: {win_rate:.0f}% ({wins}W-{losses}L)",
            f"🕰️ **Avg ROI**: {avg_roi:+.1f}%",
            "",
            "*🧾 INDIVIDUAL BREAKDOWN*",
            "",
            "\n".join(user_sections),
            f"_Updated: {datetime.utcnow():%Y-%m-%d %I:%M %p}_"
        ]

        await update.message.reply_text("\n".join(msg), parse_mode=ParseMode.MARKDOWN)
        return



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
