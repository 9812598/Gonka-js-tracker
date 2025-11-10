FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY src ./src

RUN uv pip install --system --no-cache-dir -e .

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]

