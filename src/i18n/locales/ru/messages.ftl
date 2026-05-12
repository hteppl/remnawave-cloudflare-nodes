# Жизненный цикл сервиса
service-started = <b>🚀 Сервис запущен</b>
    Мониторинг активен.

    { $summary }

service-stopped = <b>🛑 Сервис остановлен</b>
    Мониторинг выключен.

# Изменения статуса нод
node-became-healthy = <b>✅ Нода онлайн</b>
    { $name } ({ $address }) доступна.

    { $stats }

node-became-unhealthy = <b>❌ Нода офлайн</b>
    { $name } ({ $address }) недоступна.
    Причина: { $reason }

    { $stats }

# Операции DNS
dns-record-added = <b>📝 DNS обновлен</b>
    Добавлен { $ip } → { $domain }

dns-record-removed = <b>🗑️ DNS удален</b>
    Удален { $ip } из { $domain }

# Ошибки
dns-operation-error = <b>⚠️ Ошибка DNS</b>
    Не удалось { $action } { $ip } для { $domain }
    Ошибка: { $error }

health-check-error = <b>⚠️ Ошибка проверки</b>
    Ошибка при проверке: { $error }

# Критические состояния
all-nodes-down = <b>🔴 КРИТИЧНО: Все ноды недоступны</b>
    Все { $total } нод недоступны.
    Затронуты: { $nodes }

    DNS записи очищены. Требуется немедленное вмешательство.

all-nodes-recovered = <b>🟢 Восстановление: Ноды снова онлайн</b>
    { $online } из { $total } нод снова доступны.
    DNS записи восстановлены.

# Шаблоны форматирования
node-reason-unknown = неизвестно
node-stats-line = 📊 Ноды: { $online }/{ $total } онлайн, { $offline } офлайн, { $disabled } отключено
node-zone-line = • { $zone }: { $online }/{ $total } онлайн, { $offline } офлайн
ip-list-item = • { $ip }
service-summary-header = 📡 Домены:
service-no-zones = —
service-zone-line = • { $zone } — { $count } IP-адресов
service-api-info = 🔌 API: { $host }:{ $port }
domain-zone-line = • { $zone } (TTL: { $ttl }, Проксировано: { $proxied })
zone-added-details =
    IP-адреса:
            { $ip_list }
            TTL: { $ttl } | Проксировано: { $proxied }
zone-change-ips =
    IP-адреса:
            { $ip_list }
zone-change-ttl = TTL: { $value }
zone-change-proxied = Проксировано: { $value }

# События API
api-config-updated = <b>⚙️ Конфигурация обновлена через API</b>
    { $changes }
    От: { $ip }

api-domain-added = <b>➕ Домен добавлен через API</b>
    { $domain }
    { $details }
    От: { $ip }

api-domain-removed = <b>➖ Домен удален через API</b>
    { $domain }
    От: { $ip }

api-zone-added = <b>➕ Зона добавлена через API</b>
    { $fqdn }
    { $details }
    От: { $ip }

api-zone-updated = <b>⚙️ Зона обновлена через API</b>
    { $fqdn }
    { $changes }
    От: { $ip }

api-zone-removed = <b>➖ Зона удалена через API</b>
    { $fqdn }
    От: { $ip }

# Изменения состояния хостов
host-enabled = • { $remark } включен ✅
host-disabled = • { $remark } отключен ❌
host-group-enabled = <i>Некоторые ноды, управляющие { $address }, работают</i>
host-group-disabled = <i>Все ноды, управляющие { $address }, недоступны</i>
host-state-change = <b>🔧 Изменение состояния хостов</b>
    { $changes }
