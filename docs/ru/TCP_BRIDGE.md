# Транспорт TCP-мост

## Обзор
TCP-мост — альтернативный транспорт для туннелей Tunnellio. Он работает без обратного SSH и без SSH-ключей. **Мост реализован нативно на Python внутри клиента**, внешние бинарники не нужны.

Клиент сам открывает управляющее соединение к серверу, принимает входящие TCP-соединения и пробрасывает их к локальному сервису двусторонним копированием на `select`.

## Протокол
- Управляющий порт: 7835 (TCP)
- Сообщения: JSON-кадры, разделённые нулевым байтом, не длиннее 256 байт
- **Родной формат Tunnellio** (когда сервер возвращает `clientProtocol.hello`):
  - приветствие клиента: `{"type":"hello","hostname":"demo-app","password":"demo-secret"}`
  - приветствие сервера: `{"type":"hello","port":51000}`
  - соединение: `{"type":"connection","connectionId":"..."}`
  - принятие: `{"type":"accept","connectionId":"...","password":"..."}`
- **Формат, совместимый с bore** (запасной, когда `clientProtocol` отсутствует):
  - `ClientMessage`: `Hello(port)`, `Accept(uuid)`, `Authenticate(hmac_hex)`
  - `ServerMessage`: `Challenge(uuid)`, `Hello(port)`, `Heartbeat`, `Connection(uuid)`, `Error(msg)`
- Проверка подлинности: HMAC-SHA256 от SHA256(secret) по UUID-запросу (режим bore)

Всё это лежит в `src/tunnellio/bridge.py` и написано на стандартной библиотеке Python.

## Пароль моста
Для платных доменов сервер может требовать пароль TCP-моста. Это сделано ради закрытых демонстраций: адрес существует публично, но поднять к нему мост может только тот, кто знает пароль.

Поля API:
```json
{
  "connectionMode": "tcp_bridge",
  "tcpBridgePassword": "demo-secret"
}
```

Снять пароль:
```json
{
  "domainId": 123,
  "clearTcpBridgePassword": true
}
```

Профиль подключения возвращает:
```json
{
  "tcpBridge": {
    "passwordRequired": true,
    "clientProtocol": {
      "hello": {"type": "hello", "hostname": "demo-app"}
    }
  }
}
```

Когда `passwordRequired = true`, клиент сам:
1. берёт пароль из `tcpBridge.token`, `--tcp-bridge-password` или переменной окружения `TUNNELLIO_TCP_BRIDGE_PASSWORD`;
2. добавляет `password` в кадр приветствия;
3. добавляет `password` в кадр принятия для каждого соединения.

Если пароль неверен, сервер отвечает `invalid_bridge_password` и в сессии отказывает.

## Два способа запуска

### 1. Публичный поток без ключей (без API-токена и без SSH-ключа)
Команда `bridge` вызывает публичный `POST /v1/tcp-bridge/launch` без Bearer. Тело запроса:
```json
{"localHost": "127.0.0.1", "localPort": 3000}
```
Необязательный `hostname` задаёт заранее выбранный поддомен. Ответ содержит `connectionProfile.tcpBridge`, `requiresSshKey: false`, `requiresApiToken: false`.

```powershell
.\tunnellio.exe bridge --local-port 3000 --run --name my-bridge
```

С заранее выбранным поддоменом:
```powershell
.\tunnellio.exe bridge --domain new:my-app --local-port 3000 --run --name my-bridge
```

### 2. Поток с API-токеном (с планированием и возможностями)
Команда `connect --transport tcp-bridge` идёт обычным путём через `/v1/launch-spec` с Bearer.

```powershell
.\tunnellio.exe --token ВАШ_ТОКЕН connect --domain new:my-app --local-port 3000 --transport tcp-bridge --run --watch --name my-bridge
```

### Автоматический откат
```powershell
.\tunnellio.exe --token ВАШ_ТОКЕН connect --domain new:my-app --local-port 3000 --transport auto --run --watch --name my-auto
```

При `--transport auto` клиент сначала пробует SSH. Если процесс SSH быстро завершается или запуск не удался, следующие попытки идут через `tcp_bridge`.

## Команды

| Команда | Токен | Ключ | Точка обращения |
|---|---|---|---|
| `bridge` | не нужен | не нужен | `POST /v1/tcp-bridge/launch` (публичная) |
| `connect --transport tcp-bridge` | нужен | не нужен | `POST /v1/launch-spec` |
| `connect --transport ssh` | нужен | нужен | `POST /v1/launch-spec` |
| `connect --transport auto` | нужен | нужен | `POST /v1/launch-spec` (сначала SSH, затем tcp_bridge) |

## Обнаружение возможностей

`POST /v1/meta` может вернуть блок `tcpBridge`:
```json
{
  "tcpBridge": {
    "enabled": true,
    "protocol": "bore",
    "host": "tunnel.example.net",
    "controlPort": 7835,
    "publicBaseDomain": "tunnel.example.net",
    "requiresSshKey": false,
    "authRequired": false
  }
}
```

`POST /v1/capabilities` может вернуть расширенный блок `domains`:
```json
{
  "domains": {
    "supportedConnectionModes": ["direct", "cloud_proxy", "dual", "tcp_bridge", "auto"],
    "supportsKeylessTcpBridge": true,
    "tcpBridge": {
      "enabled": true,
      "protocol": "bore",
      "host": "tunnel.example.net",
      "controlPort": 7835,
      "publicBaseDomain": "tunnel.example.net",
      "portRange": {"min": 51000, "max": 51999},
      "supportsPreconfiguredSubdomains": true,
      "supportsGeneratedSubdomains": true,
      "requiresSshKey": false,
      "authRequired": false
    }
  }
}
```

## Поведение клиента

1. При `connectionMode = tcp_bridge` клиент **поднимает мост нативно** через `launch_bridge()` из `bridge.py`, без внешних бинарников.
2. При `connectionMode = auto` сначала пробуется SSH, затем мост.
3. Команда `bridge` идёт в публичную точку обращения без ключей, минуя `/v1/launch-spec`, `meta` и `capabilities`.
4. Клиент сохраняет в профиле `requiresSshKey`, `requiresApiToken`, `tcpBridge`, `publicUrl` и `connectionMode`.
5. Локальный закрытый ключ не требуется, если `requiresSshKey = false`.
6. API-токен не требуется, если `requiresApiToken = false`.
7. Фактический транспорт виден в журнале, в `status` и в `show-config`.
8. В снимок runtime-конфига попадают блок `tcpBridge` и `effectiveTransport`.
9. `TcpBridgeProcess` совместим по интерфейсу с `subprocess.Popen`: `pid`, `poll`, `terminate`, `kill`, `wait`.

## Профиль подключения
Ответ содержит блок `tcpBridge`:
```json
{
  "connectionProfile": {
    "connectionMode": "tcp_bridge",
    "requiresSshKey": false,
    "requiresApiToken": false,
    "publicUrl": "https://demo-app.tunnellio.site",
    "localHost": "127.0.0.1",
    "localPort": 3000,
    "tcpBridge": {
      "enabled": true,
      "protocol": "bore",
      "authRequired": false,
      "requiresSshKey": false,
      "requiresApiToken": false,
      "host": "tunnel.example.net",
      "controlPort": 7835,
      "publicPort": 51000,
      "publicBaseDomain": "tunnel.example.net",
      "hostname": "demo-app",
      "publicUrl": "https://demo-app.tunnellio.site",
      "localHost": "127.0.0.1",
      "localPort": 3000,
      "preconfiguredSubdomain": true,
      "generatedSubdomain": false,
      "token": null,
      "command": "tunnellio-bridge connect --host tunnel.example.net --control-port 7835 --hostname demo-app --local-host 127.0.0.1 --local-port 3000"
    }
  }
}
```

Если `authRequired = true`, мост сам проходит HMAC-рукопожатие с `tcpBridge.token`. Если `passwordRequired = true`, мост сам добавляет пароль в кадры приветствия и принятия.
