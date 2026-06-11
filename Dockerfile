FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup -S dockerize && adduser -S dockerize -G dockerize \
    && apk add --no-cache ca-certificates \
    && mkdir -p /app/data \
    && chown -R dockerize:dockerize /app

COPY requirements.txt ./
RUN apk add --no-cache --virtual .build-deps build-base libffi-dev openssl-dev \
    && pip install --upgrade pip \
    && pip install -r requirements.txt \
    && apk del .build-deps

COPY bot ./bot
COPY data/.gitkeep ./data/.gitkeep

RUN chown -R dockerize:dockerize /app
USER dockerize

CMD ["python", "-m", "bot.main"]
