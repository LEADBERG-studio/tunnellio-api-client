# Tunnellio CLI helper

Клиент для Tunnellio Integration API с упором на production-использование через системный OpenSSH.

## Текущий формат поставки
Этот репозиторий готовится под **вариант A**:
- пользователь сам собирает **Windows binary** из исходников;
- итоговый артефакт — `tunnellio.exe`;
- на целевой машине должен быть установлен **OpenSSH Client**;
- сам туннель по-прежнему поднимается через системный `ssh`, а клиент отвечает за API orchestration, TLS, планирование и диагностику.

## Что реализовано
- Bearer auth для POST-only API
- discovery через `POST /v1/meta`
- capability-aware planning через `POST /v1/capabilities`
- резолв existing key/domain через `POST /v1/keys/list` и `POST /v1/domains/list`
- orchestration через `POST /v1/launch-spec`
- запуск SSH через `connect --run`
- graceful completion ephemeral session через `POST /v1/sessions/complete`
- локальный e2e runner
- Windows TLS через `windows-truststore`

## Production-идея
Клиент не заменяет `ssh`. Он:
1. общается с API;
2. получает `launch-spec` / `connectionProfile`;
3. запускает системный `ssh`;
4. пишет понятные логи;
5. умеет завершать ephemeral session.

Для постоянной эксплуатации туннеля клиент лучше запускать под внешним supervisor:
- Windows: NSSM / WinSW / Task Scheduler
- Linux: systemd / supervisor

## Требования
### Для запуска из исходников
- Python 3.11+
- OpenSSH Client в PATH

### Для production binary на Windows
- собранный `tunnellio.exe`
- установленный OpenSSH Client

## Быстрый старт из исходников
```powershell
python -m pip install -e .
python -m tunnellio.cli --token YOUR_TOKEN meta
```

## Сборка Windows binary из исходников
Полная инструкция: `docs/BUILD_WINDOWS.md`

Коротко:
```powershell
python -m pip install -e .
python -m pip install -r requirements-build.txt
.\scripts\build_windows_binary.ps1
.\scripts\build_release_archive.ps1
```

## Основные команды
### API metadata
```powershell
python -m tunnellio.cli --token YOUR_TOKEN --verbose meta
```

### Capabilities
```powershell
python -m tunnellio.cli --token YOUR_TOKEN capabilities
```

### План для нового persistent domain
```powershell
python -m tunnellio.cli --token YOUR_TOKEN plan --domain new:mcp-dev --key existing:work-laptop --domain-lifetime-days 30 --local-port 3000 --save-profile
```

### План для random ephemeral domain
```powershell
python -m tunnellio.cli --token YOUR_TOKEN plan --domain random --key existing:work-laptop --local-port 3000
```

### Запуск SSH и auto-complete ephemeral session
```powershell
python -m tunnellio.cli --token YOUR_TOKEN connect --domain random --key existing:work-laptop --local-port 3000 --run
```

## Локальные тесты
### API-only
```powershell
.\run_local_e2e.ps1 -Token "YOUR_TOKEN" -Mode api -VerboseOutput
```

### Full e2e
```powershell
.\run_local_e2e.ps1 -Token "YOUR_TOKEN" -Mode full -VerboseOutput
```

Подробности: `LOCAL_E2E_TESTS.md` и `docs/TESTING.md`

## Файлы сборки и релизов
- `requirements-build.txt` — зависимости для сборки binary
- `tunnellio.spec` — конфигурация PyInstaller
- `scripts/build_windows_binary.ps1` — сборка `.exe` и staging release-папки
- `scripts/build_release_archive.ps1` — упаковка staging-папки в `.zip`

## Документация
- `docs/README.md`
- `docs/BUILD_WINDOWS.md`
- `docs/OPERATIONS.md`
- `docs/TESTING.md`
- `docs/VERSIONING.md`
- `docs/RELEASES.md`

## Контроль версий
Репозиторий подготовлен под старт git-версирования:
- `.gitignore` добавлен
- версия проекта хранится в `pyproject.toml` и `src/tunnellio/__init__.py`
- changelog: `CHANGELOG.md`

## Реальные API endpoints
- `POST /v1/meta`
- `POST /v1/capabilities`
- `POST /v1/keys`
- `POST /v1/keys/list`
- `POST /v1/domains`
- `POST /v1/domains/list`
- `POST /v1/domains/check`
- `POST /v1/domains/connection-profile`
- `POST /v1/sessions/complete`
- `POST /v1/launch-spec`
