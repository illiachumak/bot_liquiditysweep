#!/bin/bash

# Три способа перезапустить бот после исправления

echo "Выберите способ перезапуска:"
echo ""
echo "1. Простой (используйте скрипт)"
echo "2. Быстрый (одна команда)"  
echo "3. Пошаговый (вручную)"
echo ""
read -p "Выбор [1-3]: " choice

case $choice in
    1)
        echo "Запускаем скрипт REBUILD.sh..."
        ./REBUILD.sh
        ;;
    2)
        echo "Выполняем быстрый перезапуск..."
        docker-compose down && docker-compose build --no-cache && docker-compose up -d && echo "" && echo "✅ Готово! Смотрите логи:" && docker-compose logs -f
        ;;
    3)
        echo ""
        echo "Выполните команды по очереди:"
        echo ""
        echo "  docker-compose down"
        echo "  docker-compose build --no-cache"
        echo "  docker-compose up -d"
        echo "  docker-compose logs -f"
        echo ""
        ;;
    *)
        echo "Неверный выбор"
        exit 1
        ;;
esac
