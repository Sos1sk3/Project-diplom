FROM python:3.11-slim-bullseye

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpq-dev \
    postgresql-client \
    netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

# Добавьте после COPY . .
RUN mkdir -p /app/media
RUN chmod -R 777 /app/media  # Права для записи файлов

CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]