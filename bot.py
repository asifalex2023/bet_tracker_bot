# bot.py
from functools import wraps
from datetime  import datetime, timedelta
from zoneinfo  import ZoneInfo

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config   import BOT_TOKEN, ADMIN_IDS
from database import (
    add_pick, set_result, get_pending,
    get_picks_by_user, get_all_users, reset_database,
)
from utils    import calculate_stats


# ──────────── constants & helpers ────────────
DHAKA = ZoneInfo("Asia/Dhaka")


def money(val: float) -> str:
    whole = int(val)
    return f"${whole:+}" if val.is_integer() else f"${val:+.1f}"


def period_line(label: str, profit: float, picks: int, roi: float) -> str:
    icon = "✅" if profit > 0 else "❌" if profit < 0 else "➖"
    return (
        f"├─ {label}: {money(profit)} | {picks} pick"
        f"{'s' if picks != 1 else ''} | {icon} {roi:+.1f}%"
    )


def dash_line(label: str, stats: dict) -> str:
    return (
        f"➤ {label}: {money(stats['profit'])} | {stats['count']} pick"
        f"{'s' if stats['count'] != 1 else ''} | 📈 {stats['roi']:+.1f}%"
    )


def period_key_to_label(k: str) -> str:
    return {"daily": "Today", "weekly": "This Week", "monthly": "This Month"}[k]


def rank_users(user_stats: dict, key: str, reverse=True):
    user, val = max(user_stats.items(), key=lambda x: x[key]) if reverse \
                else min(user_stats.items(), key=lambda x: x[key])
    return user, val[key]


# ── leaderboard-specific helpers ───────────────────────────
def week_meta(now: datetime) -> tuple[str, str]:
    monday = now - timedelta(days=now.weekday())
    sunday = monday + timedelta(days=6)
    return f"WEEK {now.isocalendar().week}", f"{monday:%b %d} – {sunday:%b %d}"


def wl_and_streak(picks: list[dict]) -> tuple[str, str]:
    wins   = sum(1 for p in picks if p["result"] == "win")
    losses = sum(1 for p in picks if p["result"] == "loss")

    streak = 0
    last   = None
    for p in sorted(picks, key=lambda x: x["date"], reverse=True):
        if p["result"] not in ("win", "loss"):
            break
        if last is None:
            last, streak = p["result"], 1
        elif p["result"] == last:
            streak += 1
        else:
            break

    if streak == 0:
        streak_txt = "—"
    else:
        icon = "🔥" if last == "win" and streak > 1 else "✔️" if last == "win" else "❌"
        streak_txt = f"{icon}{streak}{'W' if last == 'win' else 'L'}"

    return f"{wins}-{losses}", streak_txt


def updated_stamp() -> str:
    return f"⌚ Updated: {datetime.now(DHAKA):%Y-%m-%d – %I:%M %p}"


# ─────────── admin guard decorator ───────────
def admin_required(handler):
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *a, **kw):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text(
                "🚫 *Sorry, this bot can only be used by @asifalex.*",
                parse_mode=ParseMode.MARKDOWN,
            )
            return
        return await handler(update, context, *a, **kw)
    return wrapper


# ─────────── public commands ───────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎉 *Welcome to the Betting Tracker Bot!*\n"
        "Created with ❤️ by @asifalex\n\n"
        "Type /commands to see everything I can do.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 *Command list*\n"
        "-  `/addpick <user> <odds> <stake>` – add a new pick\n"
        "-  `/setresult <id> <win/loss>` – close a pick\n"
        "-  `/pending` – show all open bets\n"
        "-  `/stats all` – comprehensive stats\n"
        "-  `/leaderboard [weekly|monthly|lifetime]` – rankings\n"
        "-  `/summary` – quick group overview\n"
        "-  `/resetdb` – wipe database (admin only)"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ─────────── protected commands ───────────
@admin_required
async def addpick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user, odds, stake = context.args
        add_pick(user.strip(), float(odds), float(stake))
        await update.message.reply_text(
            f"🎯 New pick saved!\n👤 *{user}* | Odds *{odds}* | 💵 *{stake}*",
            parse_mode=ParseMode.MARKDOWN,
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
        f"🆔 *{d['short_id']}* | 👤 *{d['user']}* | Odds {d['odds']} | 💵 {d['stake']}"
        for d in get_pending()
    ]
    text = "⏳ *Pending Picks*\n" + ("\n".join(rows) if rows else "— none —")
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# ─────────── /stats (kept as-is) ───────────
#  <–– your long stats handler stays unchanged ––>


# ─────────── LEADERBOARD ───────────

@admin_required
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # period via command or button
    if update.message:
        period = context.args.lower() if context.args else "weekly"
    else:
        period = getattr(context, "data", "weekly")

    if period not in ("weekly", "monthly", "lifetime"):
        await update.message.reply_text("⚠️ Usage: /leaderboard [weekly|monthly|lifetime]")
        return

    # header
    now_local = datetime.now(DHAKA)
    if period == "weekly":
        wk, dr = week_meta(now_local)
        title = f"📊 LEADERBOARD – {wk} ({dr})"
    elif period == "monthly":
        title = f"📊 LEADERBOARD – {now_local:%B %Y}"
    else:
        title = "📊 LEADERBOARD – LIFETIME"

    # per-user stats
    rows = []
    for u in get_all_users():
        picks = list(get_picks_by_user(u, "lifetime" if period == "lifetime" else period))
        if not picks:
            continue
        st = calculate_stats(picks)
        wl, streak = wl_and_streak(picks)
        rows.append(
            dict(user=u, profit=st["profit"], roi=st["roi"],
                 picks=st["count"], wl=wl, streak=streak)
        )
    rows.sort(key=lambda x: x["profit"], reverse=True)

    if not rows:
        await update.message.reply_text("📉 No finished picks yet.")
        return

    # table
    medals = ["🥇", "🥈", "🥉"]
    body_lines = [
        f"{(medals[i] if i < 3 else '  '):<2} {r['user']:<10}"
        f"{money(r['profit']):>8} {r['roi']:+7.1f}%  {r['picks']:^3} "
        f"{r['wl']:<5} {r['streak']}"
        for i, r in enumerate(rows)
    ]

    # ───────── compose the message ─────────
    txt = (
        f"{title}\n"
        f"{updated_stamp()}\n"
        "```text\n"
        "Rank Bettor        P/L     ROI%  Pk  W-L  Streak\n"
        + "\n".join(body_lines) +
        "\n```
    )

    # inline buttons
    if period == "weekly":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📆 Monthly",  callback_data="lb_month"),
                                    InlineKeyboardButton("🏅 Lifetime", callback_data="lb_life")]])
    elif period == "monthly":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📅 Weekly",   callback_data="lb_week"),
                                    InlineKeyboardButton("🏅 Lifetime", callback_data="lb_life")]])
    else:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📅 Weekly",   callback_data="lb_week"),
                                    InlineKeyboardButton("📆 Monthly",  callback_data="lb_month")]])

    # send or edit
    if update.message:
        await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    else:
        await update.callback_query.edit_message_text(txt, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)

# ─────────── resetdb, summary, confirm_resetdb ───────────
#  <–– keep your existing implementations ––>


# ─────────── bot init ───────────
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start",       start))
app.add_handler(CommandHandler("commands",    commands))
app.add_handler(CommandHandler("addpick",     addpick))
app.add_handler(CommandHandler("setresult",   setresult))
app.add_handler(CommandHandler("pending",     pending))
app.add_handler(CommandHandler("stats",       stats))
app.add_handler(CommandHandler("leaderboard", leaderboard))
app.add_handler(CommandHandler("summary",     summary))
app.add_handler(CommandHandler("resetdb",     resetdb))

app.add_handler(CallbackQueryHandler(confirm_resetdb, pattern="^resetdb_"))
app.add_handler(CallbackQueryHandler(leaderboard_cb, pattern="^lb_"))

app.run_polling()
