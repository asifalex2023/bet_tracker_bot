def calculate_stats(picks):
    total_stake = 0
    profit = 0
    win_count = 0

    for odds, stake, result in picks:
        total_stake += stake
        if result.lower() == "win":
            profit += stake * (odds - 1)
            win_count += 1
        elif result.lower() == "loss":
            profit -= stake

    hit_rate = (win_count / len(picks)) * 100 if picks else 0
    roi = (profit / total_stake) * 100 if total_stake > 0 else 0

    return {
        "count": len(picks),
        "profit": round(profit, 2),
        "roi": round(roi, 2),
        "hit_rate": round(hit_rate, 2)
    }
