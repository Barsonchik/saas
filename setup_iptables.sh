#!/bin/bash
# Скрипт для настройки iptables для мониторинга трафика Shadowsocks

# Проверяем, запущен ли скрипт от root
if [ "$EUID" -ne 0 ]; then
    echo "Пожалуйста, запустите от root: sudo $0"
    exit 1
fi

echo "Настройка iptables для мониторинга трафика..."

# Создаём новую цепочку SS_TRAFFIC если её нет
iptables -N SS_TRAFFIC 2>/dev/null || echo "Цепочка SS_TRAFFIC уже существует"

# Очищаем старые правила
iptables -F SS_TRAFFIC

# Добавляем правила для входящего трафика (по портам назначения)
# Диапазон портов Shadowsocks: 8388-8488
for port in $(seq 8388 8488); do
    iptables -A SS_TRAFFIC -p tcp --dport $port -j RETURN
    iptables -A SS_TRAFFIC -p udp --dport $port -j RETURN
done

# Также добавляем правило для перенаправления трафика в цепочку SS_TRAFFIC
# Для отслеживания всего входящего трафика на порты Shadowsocks
iptables -I INPUT -p tcp --dport 8388:8488 -j SS_TRAFFIC
iptables -I INPUT -p udp --dport 8388:8488 -j SS_TRAFFIC

# Проверяем правила
echo ""
echo "Текущие правила в цепочке SS_TRAFFIC:"
iptables -L SS_TRAFFIC -n -v

echo ""
echo "Правила добавлены в INPUT:"
iptables -L INPUT -n -v | grep -E "(8388|SS_TRAFFIC)"

echo ""
echo "✅ Настройка iptables завершена!"
echo "Теперь мониторинг трафика будет отслеживать использование портов 8388-8488"
