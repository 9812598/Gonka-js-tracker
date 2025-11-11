# backend2 (Express + SQLite)

Простой Node.js-бэкенд для Gonka Tracker. Первая версия делает упор на простоту: Express, axios, in-memory + SQLite кэш, без фоновых задач.

## Быстрый старт

1. Установите зависимости:

   ```bash
   npm install --prefix backend2
   ```

2. Создайте файл `backend2/.env` (можно взять за основу `.env.example`).

3. Запустите сервер:

   ```bash
   npm run start --prefix backend2
   ```

Сервер слушает `http://localhost:8080`. Эндпоинты находятся под префиксом `/v1`.

## Переменные окружения

Смотрите `backend2/.env.example`. Ключевые параметры:

- `PORT` — порт сервера (по умолчанию `8080`).
- `CORS_ORIGIN` — домен фронтенда (по умолчанию `http://localhost:3000`).
- `INFERENCE_URLS` — URL(ы) внешнего API (через запятую), например `http://node2.gonka.ai:8000`.
- `CACHE_DB_PATH` — путь к SQLite БД (по умолчанию `backend2/cache.db`).
- `HTTP_TIMEOUT_MS` — таймаут HTTP запросов.

## Эндпоинты первой версии

- `GET /v1/hello` — проверка сервера.
- `GET /v1/inference/current` — минимальная сводка текущего эпохи и участников.
- `GET /v1/models/current` — текущие модели и статистика.
- `GET /v1/timeline` — упрощённая временная шкала (без событий).

### Кошельки (простая SQL‑база для списка)

- `GET /v1/wallets` — получить список сохранённых кошельков. Ответ: `{ wallets: [{ address, label, created_at }] }`
- `POST /v1/wallets` — добавить кошелёк. Тело: `{ address: string, label?: string }`. Ответ: `{ wallet: { address, label, created_at } }`
- `DELETE /v1/wallets/:address` — удалить кошелёк. Ответ: `{ deleted: boolean }`

Заглушки (501):

- `GET /v1/inference/epochs/:epochId`
- `GET /v1/models/epochs/:epochId`
- `GET /v1/participants/:participantId`
- `GET /v1/participants/:participantId/inferences`

## Структура

- `src/config.js` — конфиг и env.
- `src/db.js` — SQLite-кэш (better-sqlite3).
- `src/client.js` — HTTP-клиент к внешнему API с ротацией URL.
- `src/service.js` — простая бизнес-логика и кэширование.
- `src/router.js` — маршруты `/v1/...`.
- `src/server.js` — запуск Express.

## Совместимость с фронтендом

Vite-прокси ожидает бэкенд на `http://localhost:8080` и пути `/v1/...`. Форматы ответов упрощены, но совместимы с основными экранами (модели, инференс текущей эпохи, таймлайн).

## Дальше

- Добавить фоновые задачи и полноценный кэш в SQLite.
- Расширить участники/детали/история эпох.
- Улучшить схему типов и валидацию.