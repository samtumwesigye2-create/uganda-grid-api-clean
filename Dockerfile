FROM python:3.12-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

# Vector 5250 keeps using /app/vector5250.db internally. In production we
# redirect that file onto a mounted Railway volume. Mount a volume at /data
# (or set VECTOR5250_DATA_DIR to another mounted path).
CMD ["sh", "-c", "set -e; DATA_DIR=${VECTOR5250_DATA_DIR:-/data}; mkdir -p \"$DATA_DIR\"; if [ -e /app/vector5250.db ] && [ ! -L /app/vector5250.db ] && [ ! -e \"$DATA_DIR/vector5250.db\" ]; then cp /app/vector5250.db \"$DATA_DIR/vector5250.db\"; fi; rm -f /app/vector5250.db; ln -s \"$DATA_DIR/vector5250.db\" /app/vector5250.db; exec uvicorn railway_entrypoint:app --host 0.0.0.0 --port ${PORT}"]
