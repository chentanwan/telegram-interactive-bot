FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    ASSETS_DIR=/app/assets

WORKDIR /app

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY hermesdesk ./hermesdesk
COPY assets ./assets

RUN useradd --create-home --uid 1000 hermes \
    && mkdir -p /app/data \
    && chown -R hermes:hermes /app

USER hermes

CMD ["python", "-m", "hermesdesk"]
