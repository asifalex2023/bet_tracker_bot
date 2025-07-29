```markdown
# 🎲 Betting Tracker Telegram Bot

Welcome to **Betting Tracker Bot**, your handy companion for managing bets and tracking stats on Telegram – lovingly crafted by [@asifalex](https://t.me/asifalex) ❤️.

---

## ✨ Features

- 🎯 **Add Picks** &nbsp;&nbsp;`/addpick   `
- ✔️ **Set Results** &nbsp;&nbsp;`/setresult  `
- ⏳ **Pending Picks** &nbsp;&nbsp;`/pending`
- 📊 **Stats Dashboard** &nbsp;&nbsp;`/stats  [daily|weekly|monthly]`
- 🏆 **Leaderboard** &nbsp;&nbsp;`/leaderboard [daily|weekly|monthly]`
- 🗑️ **Admin Reset** &nbsp;&nbsp;`/resetdb` (with confirmation)
- 🔐 **Admin-Only Commands** – everyone else gets a polite “🚫 Sorry, admin only” message

---

## 🖥️ Self-Host on a VPS (systemd)

> Tested on Ubuntu 20.04/22.04 with Python 3.10+

### 1. Clone & install

```
sudo apt update && sudo apt install -y python3 python3-pip git
git clone https://github.com/YOUR_USERNAME/betting-tracker-bot.git
cd betting-tracker-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` should include:

```
python-telegram-bot==20.*
pymongo==4.*
```

### 2. Configure

Edit `config.py`:

```
BOT_TOKEN  = "YOUR_BOT_TOKEN_HERE"
ADMIN_IDS  = [123456789]          # telegram user-id(s) allowed to manage bets
```

Make sure your MongoDB Atlas URI in `database.py` is correct.

### 3. Create a service

```
sudo nano /etc/systemd/system/bettingbot.service
```

```
[Unit]
Description=Betting Tracker Telegram Bot
After=network.target

[Service]
User=YOUR_SSH_USER
WorkingDirectory=/path/to/betting-tracker-bot
ExecStart=/usr/bin/python3 /path/to/betting-tracker-bot/bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable & start:

```
sudo systemctl daemon-reload
sudo systemctl enable bettingbot
sudo systemctl start  bettingbot
sudo systemctl status bettingbot
```

View logs:

```
sudo journalctl -fu bettingbot
```

The bot restarts automatically on crashes and boots with the server.

---

## 📝 Command Reference

| Command | Purpose |
|---------|---------|
| `/start` | Welcome screen |
| `/commands` | Show full command list |
| `/addpick   ` | Add a new bet |
| `/setresult  ` | Record result |
| `/pending` | List open bets |
| `/stats  [daily\|weekly\|monthly]` | Performance stats |
| `/leaderboard [daily\|weekly\|monthly]` | Top bettors |
| `/resetdb` | Wipe DB (admin only, with confirm) |

---

## 🤝 Contributing

Pull requests, issues and feature requests are welcome!  
Fork the repo, create a branch, commit your changes and open a PR.

---

## 📜 License

MIT – do what you like, just keep the credits. Enjoy and good luck! 🍀
```