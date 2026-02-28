# Shadowsocks Manager (SaaS)

**Управление серверами Shadowsocks через веб-интерфейс с поддержкой Docker и MongoDB.**

---

## 📌 Описание проекта

Этот проект предоставляет веб-интерфейс для управления конфигурациями Shadowsocks, мониторинга трафика и интеграции с MongoDB для хранения данных. Проект упакован в Docker-контейнер для простого развертывания.

---

## 🚀 Быстрый старт

### 1. Предварительные требования
- Установленный [Docker](https://docs.docker.com/get-docker/) и [Docker Compose](https://docs.docker.com/compose/install/).
- Доступ к серверу с публичным IP (для Shadowsocks).
- MongoDB (можно развернуть локально или использовать облачный сервис).

---

### 2. Настройка
#### 2.1. Клонируйте репозиторий
```bash
git clone https://github.com/Barsonchik/saas.git
cd saas
```

#### 2.2. Создайте `.env` файл
На основе `.env.example` создайте `.env` и укажите параметры подключения к MongoDB и другие переменные:
```ini
MONGO_URI=mongodb://admin:firefly2007@155.212.224.2:27017/shadowsocks_db?authSource=admin&directConnection=true
MONGO_DB=shadowsocks_db
SHADOWSOCKS_CONFIG=/etc/shadowsocks-libev/config.json
SS_SERVER_IP=155.212.224.2
```

#### 2.3. Соберите Docker-образ
```bash
docker build -t shadowsocks-manager:sync .
```

---

### 3. Запуск
#### 3.1. Запустите контейнер
```bash
docker-compose up -d
```
Или вручную:
```bash
docker run -d \
  --name ss-manager \
  --privileged \
  --cap-add=SYS_ADMIN \
  --pid=host \
  --network host \
  -v /:/host:ro \
  -v /run/systemd/system:/run/systemd/system \
  -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
  -v /var/run/dbus/system_bus_socket:/var/run/dbus/system_bus_socket \
  -v /usr/bin/systemctl:/usr/bin/systemctl:ro \
  -v /usr/bin/nsenter:/usr/bin/nsenter:ro \
  -v /etc/systemd/system:/etc/systemd/system:ro \
  -v /etc/shadowsocks-libev:/etc/shadowsocks-libev:rw \
  -v /var/log/shadowsocks-manager:/var/log/shadowsocks-manager \
  -e MONGO_URI="mongodb://admin:firefly2007@155.212.224.2:27017/shadowsocks_db?authSource=admin&directConnection=true" \
  -e MONGO_DB="shadowsocks_db" \
  -e SHADOWSOCKS_CONFIG="/etc/shadowsocks-libev/config.json" \
  -e SS_SERVER_IP="155.212.224.2" \
  shadowsocks-manager:sync
```

#### 3.2. Проверьте логи
```bash
docker logs ss-manager --tail 30
```

---

### 4. Доступ к интерфейсу
После запуска интерфейс будет доступен по адресу:
```
http://<ваш_сервер>:5000
```

---

## 📂 Структура проекта

| Директория/Файл | Описание |
|------------------|----------|
| `api/` | Основной код API (Flask/FastAPI) |
| `api/api.py` | Основные маршруты API |
| `api/config.py` | Конфигурация приложения |
| `api/config_generator.py` | Генерация конфигураций Shadowsocks |
| `api/traffic_monitor.py` | Мониторинг трафика |
| `templates/` | HTML-шаблоны для frontend |
| `static/` | Статические файлы (CSS, JS) |
| `entrypoint.sh` | Скрипт инициализации контейнера |
| `docker-compose.yml` | Конфигурация Docker Compose |
| `Dockerfile` | Инструкции для сборки образа |
| `.env.example` | Пример файла переменных окружения |

---

## 🔧 Конфигурация

### Shadowsocks
Конфигурационные файлы Shadowsocks хранятся в `/etc/shadowsocks-libev/config.json` внутри контейнера. Вы можете редактировать их через веб-интерфейс или вручную.

### MongoDB
Проект использует MongoDB для хранения данных о пользователях, трафике и конфигурациях. Убедитесь, что переменные окружения для подключения к MongoDB указаны корректно.

---

## 🛠️ Команды для управления

| Команда | Описание |
|---------|----------|
| `docker stop ss-manager` | Остановить контейнер |
| `docker rm ss-manager` | Удалить контейнер |
| `docker logs ss-manager` | Просмотреть логи |
| `docker exec -it ss-manager bash` | Зайти в контейнер |

---

## 📄 Лицензия
Проект распространяется под лицензией MIT. Подробности в файле `LICENSE`.

---

## 📬 Контакты
Автор: [Barsonchik](https://github.com/Barsonchik)
