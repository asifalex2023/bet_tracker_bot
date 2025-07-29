def calculate_stats(picks):
    total_stake = profit = win_cnt = 0.0
    for doc in picks:
        odds   = float(doc.get("odds", 0))
        stake  = float(doc.get("stake", 0))
        result = str(doc.get("result", "")).lower()
        total_stake += stake
        if result == "win":
            profit += stake * (odds - 1)
            win_cnt += 1
        elif result == "loss":
            profit -= stake

    count     = len(picks)
    hit_rate  = (win_cnt / count) * 100 if count else 0
    roi       = (profit / total_stake) * 100 if total_stake else 0   # EV

    return {
        "count": count,
        "profit": round(profit, 2),
        "roi": round(roi, 2),
        "ev": round(roi, 2),
        "hit_rate": round(hit_rate, 2)
    }
