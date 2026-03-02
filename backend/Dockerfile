FROM python:3.11-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Instala dependências do SO necessárias para o psycopg2
RUN apk add --no-cache postgresql-libs && \
    apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt && \
    apk --purge del .build-deps

COPY src/ ./src/

CMD ["python", "src/worker.py"]
