Here's a refined and professional version of you

---

````markdown
# 🎲 Betting Tracker Telegram Bot

A lightweight Telegram bot for managing betting 
with ❤️ by [@asifalex](https://t.me/asifalex).

---

## ✨ Features

- 🎯 `/addpick` – Submit a new betting pick  
- ✔️ `/setresult` – Record the outcome of a pick
- ⏳ `/pending` – View all active (unresolved) p
- 📊 `/stats [daily|weekly|monthly]` – Analyze p
- 🏆 `/leaderboard [daily|weekly|monthly]` – See
- 🗑️ `/resetdb` – Reset the database (admin only
- 🔐 Admin-only protection with polite messages 

---

## 🛠️ Self-Hosting (Ubuntu + systemd)

> Tested on Ubuntu 20.04/22.04 with Python 3.10+

### 1. Install Dependencies

```bash
sudo apt update && sudo apt install -y python3 python3-pip git
git clone https://github.com/YOUR_USERNAME/betting-tracker-bot.git
cd betting-tracker-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
````

Your `requirements.txt` should include:

```
python-telegram-bot==20.*
pymongo==4.*
```

### 2. Configuration

Edit `config.py`:

```python
BOT_TOKEN  = "YOUR_BOT_TOKEN"
ADMIN_IDS  = [123456789]  # Replace with Telegram user ID(s)
```

Ensure your MongoDB URI in `database.py` is correct and accessible.

### 3. Setup systemd Service

```bash
sudo nano /etc/systemd/system/bettingbot.service
```

Paste the following:

```ini
[Unit]
Description=Betting Tracker Telegram Bot
After=network.target

[Service]
User=YOUR_SSH_USER
WorkingDirectory=/path/to/betting-tracker-bot
ExecStart=/path/to/betting-tracker-bot/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Start and enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable bettingbot
sudo systemctl start bettingbot
```

Monitor logs:

```bash
sudo journalctl -fu bettingbot
```

The bot will now start with your server and restart on failures.

---
Replace YOUR_USER and /path/to/betting-tracker-bot with your actual username and project path.

🚀 You’re all set! The bot will now start automatically with your server.

Maintainer: @asifalex


## 🧾 Commands Overview

| Command                                 | Description                    |
| --------------------------------------- | ------------------------------ |
| `/start`                                | Start the bot and show welcome |
| `/commands`                             | Display all commands           |
| `/addpick`                              | Add a new bet                  |
| `/setresult`                            | Submit the result of a bet     |
| `/pending`                              | Show unresolved bets           |
| `/stats [daily\|weekly\|monthly]`       | Show betting statistics        |
| `/leaderboard [daily\|weekly\|monthly]` | Show user rankings             |
| `/resetdb`                              | Reset database (admin only)    |

---

## 🤝 Contributing

Pull requests, issues, and feature suggestions are welcome!
Fork the repo, create a new branch, push your changes, and open a PR.

---

## 📜 License

MIT License – free to use, modify, and distribute.
Just don’t forget the credits. Good luck and bet smart! 🍀

```

---

Let me know if you’d like:
- A badge section (e.g. `build`, `license`, etc.)
- A logo image at the top
- A `Dockerfile` setup section  
- A sample `.env` alternative setup

All easy to add.
```
