#!/bin/bash
set -e

PROJECT_DIR="/var/www/notime"

echo "🚀 Начинается процесс деплоя в $PROJECT_DIR..."
cd "$PROJECT_DIR"

# 1. Проверка наличия .env файла
echo "🔑 Проверка файла .env..."
if [ ! -f ".env" ]; then
  echo "❌ ОШИБКА: Файл .env не найден в $PROJECT_DIR!"
  echo "Пожалуйста, загрузите его на сервер перед запуском."
  exit 1
fi

# 2. Загрузка свежих образов из Registry
echo "⬇️  Загрузка последних версий образов..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml pull

# 3. Перезапуск сервисов
echo "🚀 Перезапуск сервисов..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans

# 4. Применение миграций базы данных
echo "⏳ Ожидание запуска backend сервиса..."
sleep 15
echo "🗄️  Применение миграций базы данных..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend uv run alembic upgrade head

# 5. Очистка
echo "🧹 Очистка старых образов..."
docker image prune -a -f

echo "✅ Деплой успешно завершен!"
