# bot.py
# bot.py  – imports
from functools             import wraps
from datetime              import datetime, timedelta     # ← add  timedelta
from zoneinfo              import ZoneInfo
from telegram              import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants    import ParseMode
from telegram.ext          import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
)

from config   import BOT_TOKEN, ADMIN_IDS
from database import (
    add_pick, set_result, get_pending,
    get_picks_by_user, get_all_users, reset_database
)
from utils    import calculate_stats
from datetime import datetime
from zoneinfo import ZoneInfo                # add alongside other imports
DHAKA = ZoneInfo("Asia/Dhaka")

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
def rank_users(users_stats, key, reverse=True):
    """Return user name and the chosen metric’s value."""
    user, value = max(users_stats.items(), key=lambda x: x[1][key]) if reverse \
                  else min(users_stats.items(), key=lambda x: x[1][key])
    return user, value[key]

# ────────── leaderboard helpers ──────────

def week_meta(now: datetime) -> tuple[str, str]:
    """Return ('WEEK 30', 'Jul 28 – Aug 3') for the given Dhaka date."""
    monday = now - timedelta(days=now.weekday())            # Monday of this week
    sunday = monday + timedelta(days=6)
    week_no = now.isocalendar().week
    range_txt = f"{monday:%b %d} – {sunday:%b %d}"
    return f"WEEK {week_no}", range_txt

def wl_and_streak(picks: list[dict]) -> tuple[str, str]:
    """Return '3-2'  and  '🔥3W' / '❌2L' / '✔️1W' / '—' """
    wins  = sum(1 for p in picks if p["result"] == "win")
    losses = sum(1 for p in picks if p["result"] == "loss")
    # streak (latest picks first)
    streak = 0
    last_type = None
    for p in sorted(picks, key=lambda x: x["date"], reverse=True):
        if p["result"] not in ("win", "loss"):
            break
        if last_type is None:
            last_type = p["result"]
            streak = 1
        elif p["result"] == last_type:
            streak += 1
        else:
            break
    if streak == 0:
        streak_txt = "—"
    else:
        icon = "🔥" if last_type == "win" and streak > 1 else "✔️" if last_type == "win" else "❌"
        streak_txt = f"{icon}{streak}{'W' if last_type=='win' else 'L'}"
    return f"{wins}-{losses}", streak_txt
# ADD this helper near the other helpers
def updated_stamp() -> str:
    return f"⌚ Updated: {datetime.now(DHAKA):%Y-%m-%d – %I:%M %p}"


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
    text = (
        "📋 *Command list*\n"
        "• `/addpick <user> <odds> <stake>` – add a new pick\n"
        "• `/setresult <id> <win/loss>` – close a pick\n"
        "• `/pending` – show all open bets\n"
        "• `/stats <all> (all data at once)` – performance stats\n"
        "• `/leaderboard (daily|weekly|monthly)` – top bettors\n"
        "• `/summary` – condensed group overview\n"
        "• `/resetdb` – wipe database (admin only)"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)



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
            " 📊 To get all your usage data at once, type: /stats all"
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
            f"_Updated: {datetime.now(DHAKA):%Y-%m-%d %I:%M %p}_"
        ]

        await update.message.reply_text("\n".join(msg), parse_mode=ParseMode.MARKDOWN)
        return


@admin_required
async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # period can come either from command args or from an inline button
    period = (context.args[0].lower() if context.args else "weekly") \
             if isinstance(update, Update) and update.message else context.data

    if period not in ("weekly", "monthly", "lifetime"):
        await update.message.reply_text("⚠️ Usage: /leaderboard [weekly|monthly|lifetime]")
        return

    # title / date range text
    now_local = datetime.now(DHAKA)
    if period == "weekly":
        wk, dr = week_meta(now_local)
        title = f"📊 LEADERBOARD - {wk} ({dr})"
    elif period == "monthly":
        title = f"📊 LEADERBOARD - {now_local:%B %Y}"
    else:
        title = "📊 LEADERBOARD - LIFETIME"

    # collect stats for every user
    rows = []
    for user in get_all_users():
        picks = list(get_picks_by_user(user, period if period != "lifetime" else "lifetime"))
        if not picks:
            continue
        st      = calculate_stats(picks)
        profit  = st["profit"]
        roi     = st["roi"]
        wl, streak = wl_and_streak(picks)
        rows.append({
            "user":   user,
            "profit": profit,
            "roi":    roi,
            "picks":  st["count"],
            "wl":     wl,
            "streak": streak,
        })

    # sort by P/L desc
    rows.sort(key=lambda x: x["profit"], reverse=True)

    if not rows:
        await update.message.reply_text("📉 No finished picks yet.")
        return
    # ───────── build the pretty table ─────────
medals = ["🥇", "🥈", "🥉"]
lines  = []
for idx, r in enumerate(rows, start=1):
    medal = medals[idx - 1] if idx <= 3 else "  "
    lines.append(
        f"{medal:<2} {r['user']:<10} {money(r['profit']):>8} "
        f"{r['roi']:+7.1f}%  {r['picks']:^3}  {r['wl']:<5} {r['streak']}"
    )

# ───────── compose the message ─────────
def updated_stamp() -> str:
    return f"⌚ Updated: {datetime.now(DHAKA):%Y-%m-%d – %I:%M %p}"

header = (
    f"{title}\n"
    f"{updated_stamp()}\n"
    "```
)
table_head  = "Rank Bettor        P/L    ROI%  Pk  W-L  Streak"
table_body  = "\n".join(lines)
footer = "```"                                         # close code block
txt = "\n".join([header, table_head, table_body, footer])

    # inline keyboard for quick switching
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("📆 Monthly",   callback_data="lb_month"),
        InlineKeyboardButton("🏅 Lifetime",  callback_data="lb_life"),
    ]]) if period == "weekly" else InlineKeyboardMarkup([[
        InlineKeyboardButton("📅 Weekly",    callback_data="lb_week"),
        InlineKeyboardButton("🏅 Lifetime",  callback_data="lb_life"),
    ]]) if period == "monthly" else InlineKeyboardMarkup([[
        InlineKeyboardButton("📅 Weekly",    callback_data="lb_week"),
        InlineKeyboardButton("📆 Monthly",   callback_data="lb_month"),
    ]])

    # send or edit message depending on origin
    if update.message:
        await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    else:
        await update.callback_query.edit_message_text(txt, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


# ---------- callback dispatcher ----------
async def leaderboard_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # map button → period and reuse the same code above
    mapping = {"lb_week": "weekly", "lb_month": "monthly", "lb_life": "lifetime"}
    period  = mapping.get(update.callback_query.data, "weekly")
    # store in context so leaderboard() can see it
    context.data = period
    await leaderboard(update, context)




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

@admin_required
async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Group-wide EV tracker summary."""
    # gather lifetime stats for every user that has finished picks
    users_stats = {}
    total_profit = total_picks = wins = 0
    total_stake  = 0.0

    for user in get_all_users():
        picks = list(get_picks_by_user(user, "lifetime"))
        if not picks:
            continue
        st = calculate_stats(picks)

        # save for later ranking
        users_stats[user] = {
            "profit": st["profit"],
            "ev":     st["ev"],
        }

        # group aggregates
        total_profit += st["profit"]
        total_picks  += st["count"]
        wins         += round(st["hit_rate"] * st["count"] / 100)
        total_stake  += sum(float(p["stake"]) for p in picks)

    losses   = total_picks - wins
    win_rate = (wins / total_picks) * 100 if total_picks else 0
    avg_roi  = (total_profit / total_stake) * 100 if total_stake else 0
    avg_ev   = (sum(u["ev"] for u in users_stats.values()) / len(users_stats)
                if users_stats else 0)

    # performance highlights
    top_earner, top_profit     = rank_users(users_stats, "profit",  True)
    worst_draw, worst_profit   = rank_users(users_stats, "profit",  False)
    value_king, top_ev         = rank_users(users_stats, "ev",      True)

    # build member list
    member_lines = [
        f"{u} » {'📈' if s['profit']>0 else '📉'} {money(s['profit'])} | ⚖️{s['ev']:.2f} EV"
        for u, s in users_stats.items()
    ]

    msg = [
        "🔋 *EV TRACKER - GROUP SUMMARY*",
        "",
        "*📊 CORE METRICS*",
        f"✅ **Net Profit**: {money(total_profit)}",
        f"📈 **Win Rate**: {win_rate:.0f}% ({wins}W-{losses}L)",
        f"🧠 **Avg EV**: {avg_ev:.2f}",
        f"💰 **Avg ROI**: {avg_roi:+.1f}%",
        f"🎯 **Total Picks**: {total_picks}",
        "",
        "*🏅 PERFORMANCE HIGHLIGHTS*",
        f"🥇 **Top Earner**: {top_earner} ({money(top_profit)})",
        f"📉 **Biggest Drawdown**: {worst_draw} ({money(worst_profit)})",
        f"⚡ **Value King**: {value_king} ({top_ev:.2f} EV)",
        "",
        "*👥 MEMBER PERFORMANCE (Lifetime)*",
        *member_lines,
        "",
        f"_Updated: {datetime.now(DHAKA):%Y-%m-%d %I:%M %p} | /stats all for details_",
    ]

    await update.message.reply_text("\n".join(msg), parse_mode=ParseMode.MARKDOWN)

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
app.add_handler(CommandHandler("summary", summary))
app.add_handler(CallbackQueryHandler(confirm_resetdb, pattern="^resetdb_"))
app.add_handler(CallbackQueryHandler(leaderboard_cb, pattern="^lb_"))

app.run_polling()
