# TCP bridge transport

## Обзор
TCP bridge — это альтернативный транспорт для туннелей Tunnellio. Он работает без reverse SSH и без SSH-ключей, что полезно для сред, где:
- исходящий SSH на портах 22/2222 закрыт;
- reverse SSH-сессия живёт слишком коротко;
- нет возможности зарегистрировать SSH public key;
- нет API-токена (публичный keyless flow).

Сервер возвращает `connectionMode = tcp_bridge` и готовую команду native bridge-клиента в `connectionProfile.tcpBridge`.

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

1. При `connectionMode = tcp_bridge` клиент запускает `tcpBridge.args`, а не SSH.
2. При `connectionMode = auto` клиент сначала пробует SSH, затем TCP bridge при отказе.
3. Команда `bridge` вызывает публичный keyless endpoint, минуя `/v1/launch-spec`, meta и capabilities.
4. Клиент сохраняет в профиле `requiresSshKey`, `requiresApiToken`, `tcpBridge`, `publicUrl`, `connectionMode`.
5. Клиент не требует локальный private key, если `requiresSshKey = false`.
6. Клиент не требует API token, если `requiresApiToken = false`.
7. В логах, `status` и `show-config` отображается фактический транспорт.
8. В runtime config snapshot включается блок `tcpBridge` и `effectiveTransport`.

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

Если `authRequired = true`, клиент обязан добавить `--secret <token>` из `tcpBridge.token`.
