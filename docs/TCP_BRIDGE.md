# TCP bridge transport

## Обзор
TCP bridge — это альтернативный транспорт для туннелей Tunnellio. Он работает без reverse SSH и без SSH-ключей, что полезно для сред, где:
- исходящий SSH на портах 22/2222 закрыт;
- reverse SSH-сессия живёт слишком коротко;
- нет возможности зарегистрировать SSH public key.

Сервер возвращает `connectionMode = tcp_bridge` и готовую команду native bridge-клиента в `connectionProfile.tcpBridge`.

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

## CLI

### Явный TCP bridge
```powershell
.\tunnellio.exe --token YOUR_TOKEN connect --domain new:demo-app --local-port 3000 --transport tcp-bridge --run --watch --name demo-bridge
```

### Auto-fallback
```powershell
.\tunnellio.exe --token YOUR_TOKEN connect --domain new:demo-app --local-port 3000 --transport auto --run --watch --name demo-auto
```

При `--transport auto` клиент сначала пробует SSH. Если SSH-процесс быстро завершается или launch fails, клиент переключается на `tcp_bridge` для последующих попыток.

### Флаг `--transport`
- `ssh` — только reverse SSH (по умолчанию);
- `tcp-bridge` — только TCP bridge, SSH-ключ не нужен;
- `auto` — сначала SSH, потом TCP bridge при быстром отказе.

## Поведение клиента

1. При `connectionMode = tcp_bridge` клиент запускает `tcpBridge.args`, а не SSH.
2. При `connectionMode = auto` клиент сначала пробует SSH, затем TCP bridge при отказе.
3. Клиент сохраняет в профиле `requiresSshKey`, `tcpBridge`, `publicUrl`, `connectionMode`.
4. Клиент не требует локальный private key, если `requiresSshKey = false`.
5. В логах, `status` и `show-config` отображается фактический транспорт.
6. В runtime config snapshot включается блок `tcpBridge` и `effectiveTransport`.

## Keyless flow
Для `tcp_bridge` клиент не передаёт поле `key` в `/v1/launch-spec`. Сервер возвращает `connectionProfile.requiresSshKey = false` и не возвращает объект `key`. Клиент:
- не включает `keyId` в `sessionOpenPayload`;
- не включает `key` в `PlanResult`;
- не требует `--key` или `--public-key-path`.

## Connection profile
Ответ содержит `tcpBridge` блок:
```json
{
  "connectionProfile": {
    "connectionMode": "tcp_bridge",
    "requiresSshKey": false,
    "publicUrl": "https://demo-app.tunnellio.site",
    "localHost": "127.0.0.1",
    "localPort": 3000,
    "tcpBridge": {
      "enabled": true,
      "protocol": "bore",
      "authRequired": false,
      "requiresSshKey": false,
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
