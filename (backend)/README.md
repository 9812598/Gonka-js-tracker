# Gonka Chain Observer Backend

FastAPI backend for Gonka Chain Observer with inference statistics tracking.

## Features

- Real-time inference statistics for current epoch
- Historical epoch statistics with height-wise caching
- SQLite database for immutable historical data
- Multi-URL Gonka Chain client with automatic failover
- Background polling every 30 seconds
- Automatic epoch transition detection

## Setup

```bash
make setup-backend
```

Or manually:
```bash
cd backend
uv sync
```

## Configuration

Set environment variables in root `config.env`:

```bash
INFERENCE_URLS=http://node2.gonka.ai:8000
CACHE_DB_PATH=cache.db
LOG_LEVEL=INFO
```

## Run

Using Makefile:
```bash
make run-app
```

Or directly:
```bash
uv run uvicorn backend.app:app --reload --host 0.0.0.0 --port 8080
```

Server starts at `http://localhost:8080`

## Test

Run all tests:
```bash
uv run pytest
```

Run specific component tests:
```bash
uv run pytest src/tests/test_service.py -v
```

Run live API verification:
```bash
uv run python scripts/test_live_api.py
```

## API

### Base
- `GET /v1/hello` - Health check endpoint

### Inference Statistics
- `GET /v1/inference/current?reload=false` - Current epoch statistics
  - Returns cached data (< 30s old) for fast response
  - Add `?reload=true` to force fresh fetch
  - Background task auto-refreshes every 30s
- `GET /v1/inference/epochs/{epoch_id}?height=X` - Historical epoch statistics
  - Without `height`: returns cached canonical data (at effective_block_height(N+1) - 10)
  - With `height`: returns data at specific height (stats can differ within same epoch)

### Response Format

```json
{
  "epoch_id": 56,
  "height": 887803,
  "participants": [
    {
      "index": "gonka1...",
      "address": "gonka1...",
      "weight": 37778,
      "current_epoch_stats": {
        "inference_count": "100",
        "missed_requests": "5",
        "validated_inferences": "95",
        "invalidated_inferences": "5"
      },
      "missed_rate": 0.0476
    }
  ],
  "cached_at": "2025-10-19T12:00:00Z",
  "is_current": true
}
```

## Architecture

### Components

1. **GonkaClient** - HTTP client with multi-URL failover
2. **CacheDB** - SQLite caching with epoch immutability
3. **InferenceService** - Business logic and epoch transitions
4. **Models** - Pydantic schemas with computed fields
5. **Router** - FastAPI endpoints with error handling

### Key Features

- **Height-wise caching**: Historical epochs cached at height-20 from next epoch start
- **Immutable data**: Once epoch finished, data never refetched
- **Automatic transitions**: Detects epoch changes and archives previous epoch
- **Missed rate calculation**: `missed_requests / (missed_requests + inference_count)`

## Development

Record test data:
```bash
uv run python scripts/record_api_data.py
```

Check linter:
```bash
uv run ruff check src/
```

## Documentation

See `planning/task-3.md` for detailed implementation notes.
