# Competitor Monitor

Веб-приложение для мониторинга цен конкурентов на воздушные шары.

## Стек

- Python 3.12
- FastAPI + Jinja2
- PostgreSQL + SQLAlchemy + Alembic
- requests, BeautifulSoup4, pandas, openpyxl (для будущего парсинга)

## Требования

- Python 3.12
- PostgreSQL 14+

## 1. Создание базы данных

Приложение использует **отдельную** базу `competitor_monitor` (не связанную с другими проектами).

```bash
# От имени суперпользователя PostgreSQL
psql -U postgres -f scripts/init_db.sql
```

Параметры подключения:

| Параметр | Значение |
|----------|----------|
| База     | `competitor_monitor` |
| Пользователь | `competitor_user` |
| Пароль   | `competitor_password` |
| Порт     | `5432` (по умолчанию) |

## 2. Установка зависимостей

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## 3. Настройка окружения

Скопируйте `.env.example` в `.env` (или используйте готовый `.env`):

```bash
copy .env.example .env
```

## 4. Миграции базы данных

```bash
alembic upgrade head
```

## 5. Тестовые данные

```bash
python seed_data.py
```

## 6. Запуск приложения

```bash
python run.py
```

Приложение будет доступно по адресу: **http://localhost:8082**

## Страницы

| URL | Описание |
|-----|----------|
| `/` | Dashboard — статистика и сравнение цен |
| `/competitors` | Управление конкурентами |
| `/products` | Наши товары и товары конкурентов |
| `/matching` | Сопоставление товаров |
| `/prices/history` | История изменений цен |
| `/delivery` | Условия доставки конкурентов |

## Статусы сопоставления

- `UNMATCHED` — не сопоставлен
- `AUTO_MATCHED` — сопоставлен автоматически
- `MANUAL_MATCHED` — сопоставлен вручную
- `IGNORED` — не учитывать

## Концепция

Сравнение идёт по **рыночным категориям**, а не по конкретным товарам.
Товары конкурентов привязываются к категории; наша цена задаётся на уровне категории.

Категории по умолчанию (создаются через `seed_data.py`):

- Латекс пастель
- Латекс хром
- Цифра 102 см
- Большие сердца и звёзды
- стеклянный шар
- Сфера
- Доставка

## Парсинг цен

Реальный парсинг реализован для конкурента **BestBalloonn** ([bestballoonn.ru](https://bestballoonn.ru/)).

Сайт на Tilda Store — на страницах товаров (`/tproduct/...`) название и цена
доступны в HTML. Сервис `app/services/parser_service.py` использует
`requests` + `BeautifulSoup4`.

Селекторы по умолчанию:

| Поле | CSS-селектор |
|------|--------------|
| Название | `h1.js-product-name` |
| Цена | `.js-product-price` |
| Цена (запас) | `meta[itemprop='price']` |

Для остальных конкурентов проверка цен работает в режиме заглушки.

## Текущий этап

- модели БД и миграции
- веб-интерфейс
- автоматическое сопоставление по названиям
- **реальный парсинг BestBalloonn**
- заглушка для остальных конкурентов

## Структура проекта

```
competitor-monitor/
├── app/
│   ├── main.py           # Точка входа FastAPI
│   ├── config.py         # Настройки
│   ├── database.py       # Подключение к PostgreSQL
│   ├── models/           # SQLAlchemy-модели
│   ├── routers/          # Маршруты (страницы)
│   ├── services/         # Бизнес-логика
│   ├── templates/        # HTML-шаблоны Jinja2
│   └── static/           # CSS
├── alembic/              # Миграции БД
├── scripts/init_db.sql   # Создание БД
├── seed_data.py          # Тестовые данные
├── run.py                # Запуск сервера
└── requirements.txt
```
