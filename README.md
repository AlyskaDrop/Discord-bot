# Weeping Ghosts — Eve Echoes Corporation Discord Bot

A full-featured Discord bot for the **Weeping Ghosts** corporation in Eve Echoes.

---

## Features

| Feature | Slash Command(s) |
|---|---|
| Screenshot-based registration | `/register` |
| ISK extraction from screenshots | `/isk_count` |
| PvP points tracking | `/pvp_report`, `/leaderboard` |
| PvE points tracking | `/pve_report` |
| Corp balance | `/balance`, `/deposit`, `/history`, `/richlist` |
| Ship loss compensation | `/compensation`, `/comp_status` |
| Corporation orders | `/orders`, `/order_create`, `/order_close` |
| Corporation shop | `/shop`, `/shop_add`, `/shop_remove` |
| Profit calculator | `/calc_profit` |
| Implant level calculator | `/calc_implant` |
| Mining income calculator | `/calc_mining` |
| Production materials calculator | `/calc_production` |
| Killboard | `/killboard`, `/post_kill` |
| AI assistant (GHOST-AI) | `/ai`, `/ai_reset` |
| Admin panel | `/admin_verify`, `/admin_credit`, `/admin_debit`, `/admin_give_role`, `/admin_remove_role`, `/admin_approve_kill`, `/admin_approve_comp`, `/admin_reject_comp`, `/admin_pending`, `/admin_members` |
| Auto-role assignment | `/autorole_add`, `/autorole_remove`, `/autorole_list`, `/autorole_run` |

---

## Requirements

- Python 3.11+
- Tesseract OCR installed on the system:
  ```bash
  # Ubuntu/Debian
  sudo apt install tesseract-ocr

  # macOS
  brew install tesseract

  # Windows: https://github.com/UB-Mannheim/tesseract/wiki
  ```

---

## Setup

### 1. Clone & install dependencies

```bash
git clone https://github.com/AlyskaDrop/Discord-bot.git
cd Discord-bot
pip install -r requirements.txt
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Fill in all the required values:

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Bot token from [Discord Developer Portal](https://discord.com/developers/applications) |
| `GUILD_ID` | Your server ID (right-click server → Copy Server ID) |
| `OPENAI_API_KEY` | OpenAI API key (optional — powers the AI agent) |
| `ADMIN_CHANNEL_ID` | Channel where admin notifications are sent |
| `LOG_CHANNEL_ID` | Channel where action logs are posted |
| `KILLBOARD_CHANNEL_ID` | Channel where approved kills are announced |
| `ADMIN_ROLE_ID` | Discord Role ID for administrators |
| `OFFICER_ROLE_ID` | Discord Role ID for officers |
| `MEMBER_ROLE_ID` | Discord Role ID assigned on registration |

### 3. Discord Developer Portal settings

In the [Discord Developer Portal](https://discord.com/developers/applications):

1. **Bot** tab → enable **Server Members Intent** and **Message Content Intent**
2. **OAuth2 → URL Generator** → select `bot` + `applications.commands` → grant permissions:
   - Manage Roles
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Add Reactions

### 4. Run the bot

```bash
python bot.py
```

---

## Architecture

```
Discord-bot/
├── bot.py               # Entry point, bot class, cog loader
├── config.py            # Configuration from .env
├── requirements.txt
├── .env.example
├── data/                # SQLite database & log file (auto-created)
├── cogs/
│   ├── registration.py  # /register, /profile
│   ├── isk_counter.py   # /isk_count
│   ├── points.py        # /pvp_report, /pve_report, /leaderboard
│   ├── balance.py       # /balance, /deposit, /history, /richlist
│   ├── compensation.py  # /compensation, /comp_status
│   ├── orders.py        # /orders, /order_create, /order_close
│   ├── shop.py          # /shop, /shop_add, /shop_remove
│   ├── calculators.py   # /calc_profit, /calc_implant, /calc_mining, /calc_production
│   ├── killboard.py     # /killboard, /post_kill
│   ├── ai_agent.py      # /ai, /ai_reset
│   ├── admin.py         # /admin_* commands
│   └── auto_roles.py    # /autorole_* commands
└── utils/
    ├── database.py      # Async SQLite helper functions
    └── ocr.py           # Screenshot / OCR parsing utilities
```

---

## Database

The bot uses a local **SQLite** database (`data/weeping_ghosts.db`) with the following tables:

- `users` — registered members
- `balance` — ISK balances
- `transactions` — balance change log
- `points` — PvP/PvE point totals
- `kills` — submitted kill reports
- `compensations` — ship loss requests
- `orders` — corp mission board
- `shop_items` — corp shop inventory
- `auto_roles` — auto-role rules

---

## OCR Accuracy Tips

Screenshot quality directly affects OCR extraction accuracy:

- Use **high-resolution** screenshots (not compressed)
- Make sure the ISK/name text is **clearly visible** and not obscured
- Screenshots should be in **PNG** format where possible
- If OCR fails, you can always provide values manually via command parameters

---

## License

MIT — see [LICENSE](LICENSE).
