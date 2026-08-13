# TCP bridge transport

## Обзор
TCP bridge — это альтернативный транспорт для туннелей Tunnellio. Он работает без reverse SSH и без SSH-ключей. **Мост реализован нативно на Python внутри клиента** — никаких внешних бинарей не требуется.

Клиент сам устанавливает control-соединение к серверу, получает входящие TCP-соединения и пробрасывает их к локальному сервису через `select`-based bidirectional copy.

## Wire protocol
- Control port: 7835 (TCP)
- Сообщения: null-delimited JSON frames (max 8192 байт, как на сервере)
- **Native Tunnellio format** (когда сервер возвращает `clientProtocol.hello`):
  - Client hello: `{"type":"hello","hostname":"demo-app","token":"brg_...","password":"demo-secret"}`
  - Server hello: `{"type":"hello","hostname":"demo-app","port":443,"publicUrl":"https://demo-app..."}`
  - Connection: `{"type":"connection","id":"...","hostname":"demo-app"}`
  - Accept: `{"type":"accept","id":"...","connectionId":"...","token":"brg_..."}`
  - Heartbeat: `{"type":"heartbeat"}` в обе стороны
  - Отказ: `{"type":"error","code":"..."}`
- Идентификатор соединения посылается под двумя именами (`id` и `connectionId`):
  сервер читает первое, старые клиенты присылали второе, и на этом расхождении
  каждое соединение отвечало `connection_not_found`.
- Тишина в control-канале — это не разрыв. Сервер шлёт heartbeat раз в 30 с,
  клиент — раз в 15 с; тот, кто считает тишину концом связи, отваливается через
  полсекунды после успешного рукопожатия.
- **Bore-compatible format** (fallback, когда `clientProtocol` отсутствует):
  - `ClientMessage`: `Hello(port)`, `Accept(uuid)`, `Authenticate(hmac_hex)`
  - `ServerMessage`: `Challenge(uuid)`, `Hello(port)`, `Heartbeat`, `Connection(uuid)`, `Error(msg)`
- Auth: HMAC-SHA256 от SHA256(secret) по UUID challenge (bore mode)

Всё реализовано в `src/tunnellio/bridge.py` на чистой стандартной библиотеке Python.

## TCP bridge password
Для платных доменов сервер может требовать пароль TCP bridge. Это для приватных демо: URL существует публично, но только клиент, знающий пароль, может подключить bridge-сессию.

API поля:
```json
{
  "connectionMode": "tcp_bridge",
  "tcpBridgePassword": "demo-secret"
}
```

Удаление пароля:
```json
{
  "domainId": 123,
  "clearTcpBridgePassword": true
}
```

Connection profile возвращает:
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

Когда `passwordRequired = true`, клиент автоматически:
1. берёт пароль из `--tcp-bridge-password` или `TUNNELLIO_TCP_BRIDGE_PASSWORD`
2. добавляет `"password"` в hello frame
3. добавляет `"password"` в accept frame для каждого соединения

Пароль **не берётся** из `tcpBridge.token`: там лежит ключ адреса, это другая
сущность. Подстановка одного вместо другого давала гарантированный
`invalid_bridge_password` на каждом домене с паролем.

Если пароль неверен, сервер возвращает `invalid_bridge_password` и отказывает в сессии.

## Ключ адреса (owner key)
Ключ выдаётся вместе с поддоменом, живёт в записи домена и приезжает в
`connectionProfile.tcpBridge.token` тому, кто этим адресом владеет. Клиент
кладёт его в поле `token` кадра `hello`.

Зачем: без него мост пускал на любое имя, а существующий сеанс с тем же именем
закрывался как `replaced`. То есть любой, кто знал чужой поддомен, забирал живой
туннель себе.

Поведение сервера:
- неверный ключ — `invalid_bridge_key`, всегда, это не настраивается;
- незнакомое имя — `unknown_hostname`;
- база недоступна — `bridge_unavailable`, а не «пускаем всех»;
- ключа нет вовсе — зависит от `TCP_BRIDGE_OWNER_KEY_REQUIRED` на сервере.
  Пока `0`: старый клиент проходит, но пишется в журнал строкой
  `bridge.legacy` — по ней видно, кого осталось обновить. После `1` —
  `bridge_key_required`.

Признак строгости виден клиенту в `tcpBridge.ownerKeyRequired`, `/v1/meta` и
`/v1/capabilities`.

## Ключ SSH здесь не участвует
Сессия моста открывается **без** `keyId`, и это штатный случай: SSH в мосту не
участвует вовсе. `POST /v1/sessions/open` принимает запрос без ключа, если режим
домена `tcp_bridge` или `auto`. Явно переданный неверный `keyId` по-прежнему
отбивается как `validation_error`, а Direct SSH без ключа так и остаётся
невозможным. `heartbeat`, `resume` и `close` ключа не требуют и не требовали.

## OAuth через мост не работает
Мост передаёт байты насквозь между посетителем и чужой программой; наш код в
этом обмене не участвует, и проверить токен негде. Домен с `connectionMode:
tcp_bridge` и `authMode: oauth` или `dual` теперь отвергается сразу, кодом
`oauth_requires_proxy` — и при создании домена, и при открытии сессии. Раньше
такой домен выглядел защищённым в консоли и был открыт всему интернету.

Токен умеет проверять только Cloud proxy: через него запрос действительно идёт
нашими руками.

## Два способа запуска

### 1. Публичный keyless flow (без API-токена, без SSH-ключа)
Команда `bridge` вызывает публичный `POST /v1/tcp-bridge/launch` без Bearer. Тело запроса:
```json
{"localHost": "127.0.0.1", "localPort": 3000}
```
Опционально `hostname` для заранее выбранного поддомена. Ответ даёт `connectionProfile.tcpBridge`, `requiresSshKey: false`, `requiresApiToken: false`.

```powershell
.\tunnellio.exe bridge --local-port 3000 --run --name my-bridge
```

С заранее выбранным поддоменом:
```powershell
.\tunnellio.exe bridge --domain new:my-app --local-port 3000 --run --name my-bridge
```

### 2. API-токен flow (с planning и capabilities)
Команда `connect --transport tcp-bridge` использует стандартный `/v1/launch-spec` с Bearer.

```powershell
.\tunnellio.exe --token YOUR_TOKEN connect --domain new:my-app --local-port 3000 --transport tcp-bridge --run --watch --name my-bridge
```

### Auto-fallback
```powershell
.\tunnellio.exe --token YOUR_TOKEN connect --domain new:my-app --local-port 3000 --transport auto --run --watch --name my-auto
```

При `--transport auto` клиент сначала пробует SSH. Если SSH-процесс быстро завершается или launch fails, клиент переключается на `tcp_bridge` для последующих попыток.

## CLI команды

| Команда | Токен | Ключ | Endpoint |
|---|---|---|---|
| `bridge` | не нужен | не нужен | `POST /v1/tcp-bridge/launch` (public) |
| `connect --transport tcp-bridge` | нужен | не нужен | `POST /v1/launch-spec` |
| `connect --transport ssh` | нужен | нужен | `POST /v1/launch-spec` |
| `connect --transport auto` | нужен | нужен | `POST /v1/launch-spec` (SSH first, then tcp_bridge) |

## Discovery

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

1. При `connectionMode = tcp_bridge` клиент **запускает мост нативно** через `launch_bridge()` из `bridge.py` — без внешних бинарей.
2. При `connectionMode = auto` клиент сначала пробует SSH, затем TCP bridge при отказе.
3. Команда `bridge` вызывает публичный keyless endpoint, минуя `/v1/launch-spec`, meta и capabilities.
4. Клиент сохраняет в профиле `requiresSshKey`, `requiresApiToken`, `tcpBridge`, `publicUrl`, `connectionMode`.
5. Клиент не требует локальный private key, если `requiresSshKey = false`.
6. Клиент не требует API token, если `requiresApiToken = false`.
7. В логах, `status` и `show-config` отображается фактический транспорт.
8. В runtime config snapshot включается блок `tcpBridge` и `effectiveTransport`.
9. `TcpBridgeProcess` совместим по интерфейсу с `subprocess.Popen` (`pid`, `poll`, `terminate`, `kill`, `wait`).

## Connection profile
Ответ содержит `tcpBridge` блок:
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
      "command": "tunnellio-bridge connect --host tunnel.example.net --control-port 7835 --hostname demo-app --local-host 127.0.0.1 --local-port 3000",
      "args": ["tunnellio-bridge", "connect", "--host", "tunnel.example.net", "--control-port", "7835", "--hostname", "demo-app", "--local-host", "127.0.0.1", "--local-port", "3000"]
    }
  }
}
```

Если `authRequired = true`, мост автоматически использует HMAC-handshake с `tcpBridge.token`.
Если `passwordRequired = true`, мост автоматически добавляет пароль в hello/accept frames.
