# Local Tunnellio test runner

Подготовлены файлы:
- `local_e2e_tests.py`
- `run_local_e2e.ps1`

Теперь раннер:
- печатает прогресс прямо в консоль;
- пишет timeline в `report.json`;
- показывает этапы API/TLS/SSH/probe/cleanup;
- показывает команду SSH и PID моста;
- умеет отдельно разрешать insecure fallback для API;
- умеет отдельно разрешать insecure probe для публичного URL.

## Что он проверяет
- TLS к API
- `meta` и `capabilities`
- CLI smoke test
- наличие `ssh` и `ssh-keygen`
- генерацию локального временного ключа
- регистрацию test key
- создание persistent domain
- получение `connectionProfile`
- запуск локального HTTP-сервера
- получение ephemeral launch-spec
- запуск SSH-моста
- проверку публичного URL по маркеру
- cleanup ресурсов

## Рекомендуемый запуск
### Полный сценарий с подробным выводом
```powershell
python .\local_e2e_tests.py --token YOUR_TOKEN --mode full --verbose --allow-insecure-tls-fallback --allow-insecure-public-url-probe
```

### Через PowerShell-обёртку
```powershell
.\run_local_e2e.ps1 -Token "YOUR_TOKEN" -Mode full -VerboseOutput -AllowInsecureTlsFallback -AllowInsecurePublicUrlProbe
```

## Если нужен только API smoke test
```powershell
python .\local_e2e_tests.py --token YOUR_TOKEN --mode api --verbose --allow-insecure-tls-fallback
```

## Что будет видно в консоли
Примеры этапов:
- старт теста
- secure TLS probe
- fallback на insecure TLS
- CLI smoke test
- генерация SSH-ключа
- создание key/domain
- запуск локального HTTP-сервера
- старт SSH bridge
- probe публичного URL
- cleanup ресурсов

## Где лежат логи
После запуска создаётся папка:
```text
test-artifacts/<run-id>/
```

В ней будут:
- `report.json`
- `ssh-stdout.log`
- `ssh-stderr.log`

## Важно
Если API или публичный URL снова падают на сертификате, это теперь будет видно отдельно:
- `--allow-insecure-tls-fallback` влияет на API-запросы
- `--allow-insecure-public-url-probe` влияет на проверку `https://...tunnellio.site`
