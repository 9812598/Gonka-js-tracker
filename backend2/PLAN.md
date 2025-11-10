# План миграции Python-бэкенда на Node.js (упрощённая первая версия)

Цель: максимально простая первая версия бэкенда на Node.js в отдельной папке `backend2`, без Docker и без сложной оптимизации. Сохраняем совместимость API с текущим фронтендом и постепенно добавляем функциональность.

## Стек первой версии
- Сервер: `Express` (минимум сложности)
- Язык: JavaScript (ESM) — без TypeScript для упрощения
- HTTP-клиент: `axios`
- Кеш в SQLite
- Конфиг: `.env` через `dotenv`
- Порт: `8080` (совместимо с Vite proxy `/api` → `http://localhost:8080`)
- CORS: разрешить `http://localhost:3000`

## API-совместимость (эндпоинты)
- `GET /v1/hello`
- `GET /v1/inference/current?reload=<bool>`
- `GET /v1/inference/epochs/:epoch_id?height=<int>`
- `GET /v1/participants/:participant_id?epoch_id=<int>&height=<int?>`
- `GET /v1/timeline`
- `GET /v1/models/current`
- `GET /v1/models/epochs/:epoch_id?height=<int?>`
- `GET /v1/participants/:participant_id/inferences?epoch_id=<int>`

Первая версия покроет минимум, чтобы фронт работал: `inference/current`, `models/current`, `timeline`, `participants/:id` и `participants/:id/inferences`.

## Этапы реализации

### Этап 1 — Инициализация проекта
- Создать папку `backend2/`
- Добавить `package.json` со скриптами: `start`, `dev`
- Установить зависимости: `express`, `axios`, `dotenv`, `cors`
- Создать структуру файлов:
  - `src/server.js` — запуск сервера, CORS, конфиг
  - `src/router.js` — роуты `/v1/...`
  - `src/client.js` — запросы к внешним API гонки (цепочка, участники, модели)
  - `src/service.js` — минимальная логика сборки ответов, без БД
  - `src/config.js` — чтение ENV и дефолты

### Этап 2 — Базовый сервер и `/v1/hello`
- Поднять Express на порту `8080`
- Включить CORS для `http://localhost:3000`
- Добавить базовый роут `GET /v1/hello` для проверки

### Этап 3 — Клиент к API гонки (минимум)
- Реализовать методы:
  - `getLatestEpoch()` — `GET /v1/epochs/latest`
  - `getLatestHeight()` — `GET /chain-rpc/status`
  - `getCurrentEpochParticipants()` — `GET /v1/epochs/current/participants`
  - `getEpochParticipants(epochId)` — `GET /v1/epochs/:epochId/participants`
  - `getAllParticipants(height?)` — `GET /chain-api/productscience/inference/inference/participant`
  - `getBlock(height)` — `GET /chain-api/.../block`
  - `getModelsAll()` — `GET /models/all`
  - `getModelsStats()` — `GET /models/stats`
  - `getEpochPerformanceSummary(epochId, participantId, height?)`

### Этап 4 — `GET /v1/inference/current`
- Собрать активных участников текущего эпока
- Слить базовые поля участника и `current_epoch_stats`
- Вернуть форму по интерфейсу фронта (`epoch_id`, `height`, `participants`, `is_current`, опционально `current_block_height`, `current_block_timestamp`, `avg_block_time`)
- Кеш в памяти (TTL ~30–60 сек), `reload=true` принудительно обновляет

### Этап 5 — `GET /v1/models/current`
- Вернуть список моделей и статистику из API, аналог `ModelsResponse`
- Добавить `is_current=true`, `epoch_id`, `height`, `cached_at`

### Этап 6 — `GET /v1/timeline`
- Получить текущий блок и опорный блок (например, `current-10000`) для оценки средней скорости блока
- Заполнить базовые события (минимально необходимое для фронта) и поля `current_epoch_index`, `epoch_length`

### Этап 7 — `GET /v1/participants/:id` и `GET /v1/participants/:id/inferences`
- Детали участника: объединить информацию из participants, seed/warm keys/модели (минимум — вернуть пустые списки, если данных нет)
- Инференсы: вернуть три массива `successful`, `expired`, `invalidated` (минимально — пустые списки, если нет данных в API)

### Этап 8 — Исторические эндпоинты
- `GET /v1/inference/epochs/:epoch_id?height=<int>`
- `GET /v1/models/epochs/:epoch_id?height=<int?>`
- Обработка `height`: если отсутствует — использовать «каноническую» высоту для эпока (минимальная логика: брать `latest_height` или `epoch_effective_height`, без сложной валидации на первом этапе)

### Этап 9 — Ошибки и валидация
- Единый формат ошибок: `{ error: 'message' }`
- Проверка параметров (`epoch_id`, `height`) и 400/404/503/500 коды как в FastAPI

### Этап 10 — Документация и запуск
- Обновить `README.md` в `backend2` с командами:
  - `npm install`
  - `npm run dev`
  - `npm start`
- Описать переменные окружения: `INFERENCE_URLS`, `PORT`, др.

## Фаза 2 (после успешной первой версии)
- Добавить фоновые задачи (поллинги) с небольшими задержками: jail, health, rewards, warm keys, hardware, models, timeline
- Добавить SQLite для персистентного кеша (портировать схему из Python)
- Расширить логику высот и канонических значений, авто‑heal total rewards
- Оптимизировать клиент (ротация `INFERENCE_URLS`, ретраи)

## Окружение и переменные
- `.env` пример:
  - `PORT=8080`
  - `INFERENCE_URLS=http://node2.gonka.ai:8000`
  - `CORS_ORIGIN=http://localhost:3000`

## Критерии готовности первой версии
- Фронтенд открывается и корректно рендерит:
  - Dashboard: текущий эпок, таблица участников
  - Models: текущие модели
  - Timeline: базовая шкала и текущие значения
  - Модалка участника: грузится без ошибок (пусть частично пустая)
- Базовые эндпоинты стабильно отвечают, без падений при ошибках внешнего API

## Пошаговое утверждение
1. Утверждаем план
2. Реализуем Этап 1–2 (скелет и `/v1/hello`)
3. Реализуем Этап 3–4 (клиент и `inference/current`)
4. Проверяем фронт, затем Этап 5–7
5. Добиваем исторические эндпоинты и документацию

---
Примечание: старый `backend/` сохраняем для референса. В первой версии сознательно упрощаем логику без БД и фоновых задач, чтобы быстрее запустить приложение.