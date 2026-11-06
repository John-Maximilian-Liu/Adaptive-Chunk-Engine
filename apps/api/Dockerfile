# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder
WORKDIR /build
RUN pip install --no-cache-dir uv
COPY apps/api/requirements.txt /build/requirements.txt
RUN uv pip install --system --no-cache -r /build/requirements.txt

FROM python:3.12-slim AS runtime
RUN useradd -m -u 10001 ace \
 && mkdir -p /data /app \
 && chown -R ace:ace /data
WORKDIR /app
COPY --from=builder /usr/local /usr/local
COPY packages/python /packages/python
COPY apps/api /app
COPY workers /app/workers
COPY contracts /contracts
ENV PYTHONPATH=/app:/packages/python \
    ACE_STORAGE_ROOT=/data \
    UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000
USER ace
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
