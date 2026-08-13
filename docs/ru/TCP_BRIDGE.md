# Транспорт TCP-мост

## Обзор
TCP-мост — альтернативный транспорт для туннелей Tunnellio. Он работает без обратного SSH и без SSH-ключей. **Мост реализован нативно на Python внутри клиента**, внешние бинарники не нужны.

Клиент сам открывает управляющее соединение к серверу, принимает входящие TCP-соединения и пробрасывает их к локальному сервису двусторонним копированием на `select`.

## Протокол
- Управляющий порт: 7835 (TCP)
- Сообщения: JSON-кадры, разделённые нулевым байтом, не длиннее 8192 байт (как на сервере)
- **Родной формат Tunnellio** (когда сервер возвращает `clientProtocol.hello`):
  - приветствие клиента: `{"type":"hello","hostname":"demo-app","token":"brg_...","password":"demo-secret"}`
  - приветствие сервера: `{"type":"hello","hostname":"demo-app","port":443,"publicUrl":"https://demo-app..."}`
  - соединение: `{"type":"connection","id":"...","hostname":"demo-app"}`
  - принятие: `{"type":"accept","id":"...","connectionId":"...","token":"brg_..."}`
  - удар сердца: `{"type":"heartbeat"}` в обе стороны
  - отказ: `{"type":"error","code":"..."}`
- Идентификатор соединения посылается под двумя именами (`id` и `connectionId`):
  сервер читает первое, старые клиенты присылали второе, и на этом расхождении
  каждое соединение отвечало `connection_not_found`.
- Тишина в управляющем канале — это не разрыв. Сервер подаёт голос раз в 30 с,
  клиент раз в 15 с; тот, кто считает тишину концом связи, отваливается через
  полсекунды после успешного рукопожатия.
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
1. берёт пароль из `--tcp-bridge-password` или переменной окружения `TUNNELLIO_TCP_BRIDGE_PASSWORD`;
2. добавляет `password` в кадр приветствия;
3. добавляет `password` в кадр принятия для каждого соединения.

Пароль **не берётся** из `tcpBridge.token`: там лежит ключ адреса, это другая
сущность. Подстановка одного вместо другого давала гарантированный
`invalid_bridge_password` на каждом домене с паролем.

Если пароль неверен, сервер отвечает `invalid_bridge_password` и в сессии отказывает.

## Ключ адреса
Ключ выдаётся вместе с поддоменом, живёт в записи домена и приезжает в
`connectionProfile.tcpBridge.token` тому, кто этим адресом владеет. Клиент
кладёт его в поле `token` кадра приветствия.

Зачем: без него мост пускал на любое имя, а существующий сеанс с тем же именем
закрывался как `replaced`. То есть любой, кто знал чужой поддомен, забирал живой
туннель себе.

Что отвечает сервер:
- неверный ключ — `invalid_bridge_key`, всегда, это не настраивается;
- незнакомое имя — `unknown_hostname`;
- база недоступна — `bridge_unavailable`, а не «пускаем всех»;
- ключа нет вовсе — зависит от `TCP_BRIDGE_OWNER_KEY_REQUIRED` на сервере.
  Пока `0`: старый клиент проходит, но попадает в журнал строкой
  `bridge.legacy`, и по ней видно, кого осталось обновить. После `1` —
  `bridge_key_required`.

Строгость видна клиенту в `tcpBridge.ownerKeyRequired`, `/v1/meta` и
`/v1/capabilities`.

## SSH-ключ здесь не участвует
Сессия моста открывается **без** `keyId`, и это штатный случай: SSH в мосту не
участвует вовсе. `POST /v1/sessions/open` принимает запрос без ключа, если режим
домена `tcp_bridge` или `auto`. Явно переданный неверный `keyId` по-прежнему
отбивается как `validation_error`, а Direct SSH без ключа так и остаётся
невозможным. `heartbeat`, `resume` и `close` ключа не требуют и не требовали.

## OAuth через мост не работает
Мост передаёт байты насквозь между посетителем и чужой программой; наш код в
этом обмене не участвует, и проверить токен негде. Домен с `connectionMode:
tcp_bridge` и `authMode: oauth` или `dual` теперь отвергается сразу, кодом
`oauth_requires_proxy`, и при создании домена, и при открытии сессии. Раньше
такой домен выглядел защищённым в консоли и был открыт всему интернету.

Токен умеет проверять только Cloud proxy: через него запрос действительно идёт
нашими руками.

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
