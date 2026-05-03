# Weeping Ghosts — Discord-бот корпорации Eve Echoes

Полнофункциональный Discord-бот для корпорации **Weeping Ghosts** в Eve Echoes.

---

## Возможности

| Функция | Слэш-команда(ы) |
|---|---|
| Регистрация по скриншоту | `/register` |
| Извлечение ISK из скриншотов | `/isk_count` |
| Учёт PvP-очков | `/pvp_report`, `/leaderboard` |
| Учёт PvE-очков | `/pve_report` |
| Баланс корпорации | `/balance`, `/deposit`, `/history`, `/richlist` |
| Компенсация потери корабля | `/compensation`, `/comp_status` |
| Задания корпорации | `/orders`, `/order_create`, `/order_close` |
| Магазин корпорации | `/shop`, `/shop_add`, `/shop_remove` |
| Калькулятор прибыли | `/calc_profit` |
| Калькулятор уровня имплантов | `/calc_implant` |
| Калькулятор дохода от майнинга | `/calc_mining` |
| Калькулятор производственных материалов | `/calc_production` |
| Доска убийств | `/killboard`, `/post_kill` |
| ИИ-ассистент (GHOST-AI) | `/ai`, `/ai_reset` |
| Панель администратора | `/admin_verify`, `/admin_credit`, `/admin_debit`, `/admin_give_role`, `/admin_remove_role`, `/admin_approve_kill`, `/admin_approve_comp`, `/admin_reject_comp`, `/admin_pending`, `/admin_members` |
| Автоматическое присвоение ролей | `/autorole_add`, `/autorole_remove`, `/autorole_list`, `/autorole_run` |

---

## Требования

- Python 3.11+
- Tesseract OCR, установленный в системе:
  ```bash
  # Ubuntu/Debian
  sudo apt install tesseract-ocr

  # macOS
  brew install tesseract

  # Windows: https://github.com/UB-Mannheim/tesseract/wiki
  ```

---

## Установка

### 1. Клонировать репозиторий и установить зависимости

```bash
git clone https://github.com/AlyskaDrop/Discord-bot.git
cd Discord-bot
pip install -r requirements.txt
```

### 2. Создать файл `.env`

```bash
cp .env.example .env
```

Заполните все обязательные поля:

| Переменная | Описание |
|---|---|
| `DISCORD_TOKEN` | Токен бота из [Discord Developer Portal](https://discord.com/developers/applications) |
| `GUILD_ID` | ID вашего сервера (ПКМ по серверу → Копировать ID сервера) |
| `OPENAI_API_KEY` | API-ключ OpenAI (необязательно — используется ИИ-агентом) |
| `ADMIN_CHANNEL_ID` | Канал для уведомлений администраторов |
| `LOG_CHANNEL_ID` | Канал для публикации журнала действий |
| `KILLBOARD_CHANNEL_ID` | Канал для анонсов подтверждённых убийств |
| `ADMIN_ROLE_ID` | ID роли Discord для администраторов |
| `OFFICER_ROLE_ID` | ID роли Discord для офицеров |
| `MEMBER_ROLE_ID` | ID роли Discord, присваиваемой при регистрации |

### 3. Настройки Discord Developer Portal

В [Discord Developer Portal](https://discord.com/developers/applications):

1. Вкладка **Bot** → включить **Server Members Intent** и **Message Content Intent**
2. **OAuth2 → URL Generator** → выбрать `bot` + `applications.commands` → выдать разрешения:
   - Manage Roles (Управление ролями)
   - Send Messages (Отправка сообщений)
   - Embed Links (Встраивание ссылок)
   - Attach Files (Прикрепление файлов)
   - Read Message History (Чтение истории сообщений)
   - Add Reactions (Добавление реакций)

### 4. Запустить бота

```bash
python bot.py
```

---

## Архитектура

```
Discord-bot/
├── bot.py               # Точка входа, класс бота, загрузчик когов
├── config.py            # Конфигурация из .env
├── requirements.txt
├── .env.example
├── data/                # База данных SQLite и лог-файл (создаются автоматически)
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
│   ├── admin.py         # команды /admin_*
│   └── auto_roles.py    # команды /autorole_*
└── utils/
    ├── database.py      # Асинхронные вспомогательные функции SQLite
    └── ocr.py           # Утилиты для разбора скриншотов / OCR
```

---

## База данных

Бот использует локальную базу данных **SQLite** (`data/weeping_ghosts.db`) со следующими таблицами:

- `users` — зарегистрированные участники
- `balance` — балансы ISK
- `transactions` — журнал изменений баланса
- `points` — суммарные очки PvP/PvE
- `kills` — отправленные отчёты об убийствах
- `compensations` — заявки на компенсацию потери корабля
- `orders` — доска заданий корпорации
- `shop_items` — ассортимент магазина корпорации
- `auto_roles` — правила автоматического присвоения ролей

---

## Советы по точности OCR

Качество скриншота напрямую влияет на точность извлечения данных через OCR:

- Используйте скриншоты в **высоком разрешении** (без сжатия)
- Убедитесь, что текст ISK/имени **чётко виден** и ничем не перекрыт
- По возможности сохраняйте скриншоты в формате **PNG**
- Если OCR не справляется, значения всегда можно ввести вручную через параметры команды

---

## Лицензия

MIT — см. [LICENSE](LICENSE).
