FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей с правильными версиями библиотек
RUN apt-get update && apt-get install -y \
    supervisor \
    curl \
    openssl \
    libssl-dev \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Создание структуры каталогов
RUN mkdir -p \
    /var/log/supervisor \
    /var/log/api \
    /app/static/css \
    /app/static/js

# Копирование файлов
COPY requirements.txt .
COPY api/ ./api/
COPY templates/ ./templates/
COPY static/ ./static/  
COPY supervisord.conf /etc/supervisor/conf.d/
COPY entrypoint.sh .

# Обновите pip и установите Python зависимости
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Права
RUN chmod +x entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]