# Tunnellio CLI

Полностью самодостаточный клиент для Tunnellio Integration API. TCP bridge реализован нативно на Python — без внешних бинарей.

## Формат поставки
Поддерживаются два сценария:

1. **Сборка из исходников** — Python 3.11+, `pip install .`
2. **Готовый релизный бинарник** (Windows) — Python не нужен на целевой машине

### Требования по транспорту
| Транспорт | Что нужно | Где работает |
|---|---|---|
| `bridge` (native TCP bridge) | только Python | Windows, Linux, macOS |
| `connect --transport tcp-bridge` | только Python | Windows, Linux, macOS |
| `connect --transport ssh` | Python + OpenSSH | везде, где есть SSH |
| `connect --transport auto` | Python + OpenSSH | везде |

**TCP bridge не требует внешних бинарей.** Мост реализован внутри клиента на чистом Python.

## Что реализовано
- Bearer auth для POST-only API
- discovery через `POST /v1/meta`
- capability-aware planning через `POST /v1/capabilities`
- orchestration через `POST /v1/launch-spec`
- **TCP bridge transport** (`connectionMode = tcp_bridge`) — keyless альтернатива reverse SSH
- **`--transport` флаг** (`ssh`, `tcp-bridge`, `auto`) для явного выбора транспорта
- **auto-fallback** с SSH на TCP bridge при быстром отказе SSH
- запуск SSH через `connect --run`
- supervised mode через `connect --run --watch`
- health-check публичного URL
- автоматический restart туннеля при обрыве SSH или деградации health-check
- локальный runtime registry
- обязательное runtime-имя у каждого туннеля
- авто-генерация имени, если оно не задано явно
- просмотр активных managed tunnels через `status`
- адресная остановка tunnel по имени через `stop --name`
- получение runtime config / connection params по имени через `show-config --name`
- запуск через default config и client config
- образец полного конфига `config.example.json`
- автоматика обновления default config перед запуском
- управляемая перезапись client config (`ask` / `yes` / `no`)
- structured status file
- readable runtime logs
- graceful completion ephemeral session через `POST /v1/sessions/complete`
- session-aware runtime cycle: `open -> heartbeat -> resume -> close`
- OAuth discovery через `GET /.well-known/oauth-authorization-server`
- protected resource metadata через `GET /.well-known/oauth-protected-resource`
- server-side OAuth Authorization Code + PKCE flow через `POST /oauth/authorize` и `POST /oauth/token`
- CLI-команды `oauth-login`, `oauth-refresh`, `oauth-introspect`
- локальное хранение OAuth token record с `accessToken`, `refreshToken`, `scope`, `issuer`, endpoint-ами и привязкой к client/domain
- сохранение старого `refreshToken`, если refresh-response не вернул новый
- config-поля `requestedAuthMode`, `connectionMode`, `oauthClientPolicy`, `runtimeName`, `useDiscovery`, `sessionStrategy`, `enablePkce`, `transport`
- сервер остаётся источником истины по итоговому `authMode` / `connectionMode`; клиент проверяет и отражает фактический результат
- локальный e2e runner
- Windows TLS через `windows-truststore`

## Почему это важно не только для пользователя, но и для интеграции
Принятые правки нужны не только для удобства ручного использования.
Они закрывают и обязательный интеграционный сценарий:

- туннель может подниматься вызывающим приложением;
- домен может быть не фиксированным, а случайным или эфемерным;
- после запуска вызывающее приложение должно уметь не только останавливать и проверять туннель, но и получать из клиента фактические серверные параметры подключения;
- минимум — конечный домен / hostname / public URL.

Именно для этого у каждого managed tunnel теперь есть runtime name и runtime config snapshot, доступный по имени.

## Конфигурационная модель
Клиент работает через конфиг как через канонический источник запуска.

### Default config
Если явный `--config` не передан, используется default config:
- путь по умолчанию: `~/.tunnellio/default-launch.json`
- если запуск сделан с CLI-флагами, клиент **сначала обновляет default config**, затем **запускается уже с него**
- после этого можно просто запускать бинарник без аргументов

### Client config
Если передан `--config path\\to\\client.json`, тогда этот config считается клиентским.

Поведение при запуске с CLI-параметрами и явным config:
1. если config уже существует и параметры меняют его содержимое, клиент спрашивает — переписывать или нет;
2. `--config-overwrite yes` — переписывает config и запускается с обновлённого файла;
3. `--config-overwrite no` — файл **не** переписывает, но в текущем запуске CLI-параметры имеют приоритет над совпадающими полями конфига;
4. если config не существует, он создаётся и запуск идёт уже с него.

## Имя туннеля
Теперь **у каждого managed tunnel всегда есть имя**.

- если имя задано явно через `--name`, используется оно;
- если имя не задано, клиент генерирует его автоматически;
- имя попадает в runtime registry;
- имя видно в `status`;
- по имени можно:
  - получить статус;
  - остановить туннель;
  - получить runtime config с параметрами подключения.

## Что вызывает приложение при случайном домене
Если вызывающее приложение использует `random` / `ephemeral` домен, оно не должно полагаться только на исходные параметры запуска.
После старта оно должно получить из клиента уже разрешённые сервером данные подключения.

Рекомендуемый поток:
1. запустить туннель и по возможности сразу задать `--name`;
2. дождаться появления runtime entry;
3. вызвать:
```powershell
.\tunnellio.exe show-config --name app-backend
```
4. считать из ответа фактический домен / public URL / connection data;
5. дальше использовать то же имя для `status --name` и `stop --name`.

## TCP bridge: туннель без SSH-ключей и без API-токена
TCP bridge — это самый простой способ поднять туннель. Команда `bridge` не требует ни SSH-ключа, ни API-токена.

### Мгновенный туннель (без токена, без ключа)
```powershell
.\tunnellio.exe bridge --local-port 3000 --run --name my-bridge
```
Клиент вызовет публичный `POST /v1/tcp-bridge/launch` без Bearer, получит `connectionProfile.tcpBridge` и запустит мост.

### С заранее выбранным поддоменом
```powershell
.\tunnellio.exe bridge --domain new:my-app --local-port 3000 --run --name my-bridge
```

### Получить план без запуска (JSON)
```powershell
.\tunnellio.exe bridge --local-port 3000 --output json
```

### TCP bridge через API-токен (с planning и capabilities)
```powershell
.\tunnellio.exe --token YOUR_TOKEN connect --domain new:my-app --local-port 3000 --transport tcp-bridge --run --watch --name my-bridge
```

### Auto-fallback (сначала SSH, потом TCP bridge)
```powershell
.\tunnellio.exe --token YOUR_TOKEN connect --domain new:my-app --local-port 3000 --transport auto --run --watch --name my-auto
```

В логах видно фактический транспорт и публичный TCP port. В `status` и `show-config` транспорт тоже отражается.

## Готовый бинарник: базовое использование
### Seed default config и запуск supervised tunnel
```powershell
.\tunnellio.exe --token YOUR_TOKEN connect --domain existing:mcp --local-port 3000 --run --watch --name prod-api --health-path / --log-file .\logs\tunnel.log
```

### Повторный запуск только из default config
```powershell
.\tunnellio.exe
```

### Запуск по client config
```powershell
.\tunnellio.exe --config .\configs\prod-api.json
```

## OAuth: быстрые команды
### Логин через server-side OAuth flow
```powershell
.\tunnellio.exe --token YOUR_TOKEN oauth-login --domain existing:test --client-id YOUR_CLIENT_ID --redirect-uri http://localhost:3333/callback --scopes "proxy.connect proxy.inspect" --token-name test-client --use-discovery --enable-pkce
```

### Refresh сохранённого OAuth token
```powershell
.\tunnellio.exe --token YOUR_TOKEN oauth-refresh --token-name test-client
```

### Introspect сохранённого OAuth token
```powershell
.\tunnellio.exe --token YOUR_TOKEN oauth-introspect --token-name test-client
```

## Управление активными туннелями
### Показать все managed tunnels
```powershell
.\tunnellio.exe status
```

### Показать статус tunnel по имени
```powershell
.\tunnellio.exe status --name prod-api
```

### Остановить tunnel по имени
```powershell
.\tunnellio.exe stop --name prod-api
```

### Остановить все активные managed tunnels
```powershell
.\tunnellio.exe stop --all
```

### Получить runtime config и connection params по имени
```powershell
.\tunnellio.exe show-config --name prod-api
```

## Файлы конфигурации
- `config.example.json` — полный образец конфига проекта
- `~/.tunnellio/default-launch.json` — автоматически поддерживаемый default config
- `~/.tunnellio/configs/` — рекомендуемое место для client config-файлов
- `~/.tunnellio/state/runtimes/*.json` — runtime status
- `~/.tunnellio/state/runtimes/*.config.json` — runtime config snapshots

## Документация
- `docs/README.md`
- `docs/BUILD_WINDOWS.md`
- `docs/CONFIGS.md`
- `docs/TCP_BRIDGE.md`
- `docs/INTEGRATION.md`
- `docs/OPERATIONS.md`
- `docs/TESTING.md`
- `docs/VERSIONING.md`
- `docs/RELEASES.md`
