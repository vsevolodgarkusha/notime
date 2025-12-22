#!/bin/bash

# Прекратить выполнение скрипта при любой ошибке
set -e

# --- КОНФИГУРАЦИЯ ---
# Префикс для ваших образов в Docker Hub
REGISTRY_PREFIX="vsevolodg/notime"
# Тег для образов. 'latest' — для простоты.
# Для лучшего контроля версий рекомендуется использовать хеш коммита: $(git rev-parse --short HEAD)
TAG="latest"

# Определяем сервисы и папки, в которых они лежат
SERVICE_NAMES=("llm-service" "backend" "frontend" "telegram-bot")
SERVICE_DIRS=("llm_service" "backend" "frontend" "telegram_bot")

# --- СБОРКА И ЗАГРУЗКА ---


# Перебираем и собираем каждый сервис
for i in "${!SERVICE_NAMES[@]}"; do
  SERVICE_NAME=${SERVICE_NAMES[$i]}
  DIR=${SERVICE_DIRS[$i]}
  IMAGE_NAME="$REGISTRY_PREFIX-$SERVICE_NAME:$TAG"

  echo ""
  echo "--------------------------------------------------"
  echo "Сборка multi-platform образа для: $IMAGE_NAME"
  echo "--------------------------------------------------"
  # Используем buildx для сборки под amd64 (сервер) и arm64 (ваш Mac)
  # Флаг --push сразу загружает результат в Docker Hub
  docker buildx build --platform linux/amd64,linux/arm64 -t "$IMAGE_NAME" --push "$DIR"

done

echo ""
echo "✅ Все образы успешно собраны и загружены в Docker Hub!"
echo "Образы для celery-worker и celery-beat не собираются отдельно, так как они используют образ 'backend'."
