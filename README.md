# Tunnellio CLI helper

Клиент для Tunnellio Integration API с упором на production-использование через системный OpenSSH.

## Формат поставки
Поддерживаются два сценария:

1. **Сборка из исходников** для разработчика или администратора
2. **Готовый релизный бинарник** для конечного пользователя

### Важный нюанс
Для сборки бинарника из исходников нужна подготовленная build-среда:
- Python 3.11+
- pip
- build dependencies
- OpenSSH Client для тестов и runtime-проверок

Но **для использования готового релизного бинарника Python на целевой машине не нужен**.
Нужны только:
- `tunnellio.exe`
- системный OpenSSH Client
- токен API

## Что реализовано
- Bearer auth для POST-only API
- discovery через `POST /v1/meta`
- capability-aware planning через `POST /v1/capabilities`
- orchestration через `POST /v1/launch-spec`
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
- `docs/INTEGRATION.md`
- `docs/OPERATIONS.md`
- `docs/TESTING.md`
- `docs/VERSIONING.md`
- `docs/RELEASES.md`
