# utils.py
def calculate_stats(picks):
    total_stake = profit = win_count = 0.0

    for doc in picks:
        odds   = float(doc.get("odds", 0))
        stake  = float(doc.get("stake", 0))
        result = str(doc.get("result", "")).lower()

        total_stake += stake
        if result == "win":
            profit += stake * (odds - 1)
            win_count += 1
        elif result == "loss":
            profit -= stake

    count    = len(picks)
    hit_rate = (win_count / count) * 100 if count else 0
    roi      = (profit / total_stake) * 100 if total_stake else 0

    return {
        "count":   count,
        "profit":  round(profit, 2),
        "roi":     round(roi, 2),   # keep old key so nothing breaks
        "ev":      round(roi, 2),   # new alias that the bot will show
        "hit_rate":round(hit_rate, 2)
    }
