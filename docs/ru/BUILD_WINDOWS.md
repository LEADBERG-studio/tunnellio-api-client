# Сборка бинарника под Windows

## Что получается
- файл `tunnellio.exe`;
- транспорт туннеля — системный `ssh`;
- на целевой машине должен быть клиент OpenSSH.

TCP-мост в этом бинарнике работает и без OpenSSH: он реализован внутри клиента.

## Поведение готового бинарника
- у каждого управляемого туннеля есть имя запуска;
- если имя не передано, клиент порождает его сам;
- имена видны в `status`;
- туннель можно остановить по имени;
- параметры подключения читаются по имени.

## Команда сборки
```powershell
.\scripts\build_windows_binary.ps1
```

## Что появляется на выходе
- `dist\tunnellio.exe`
- `artifacts\tunnellio-windows-x64-v<версия>\` — только локальная папка подготовки

## Важное правило упаковки
Бинарник под Windows — самостоятельный артефакт. В универсальный архив исходников он **не** входит.

## Универсальный архив исходников
Собирается отдельно:
```powershell
.\scripts\build_release_archive.ps1
```

Результат:
- `artifacts\tunnellio-source-v<версия>.zip`

Архив не зависит от системы и содержит файлы Python-проекта, а не бинарник.

## Команды после сборки
### Запомнить параметры и поднять именованный туннель
```powershell
.\dist\tunnellio.exe --token ВАШ_ТОКЕН connect --domain existing:mcp --local-port 3000 --run --watch --name prod-api
```

### Запуск от сохранённого конфига
```powershell
.\dist\tunnellio.exe
```

### Перечислить имена
```powershell
.\dist\tunnellio.exe status
```

### Состояние одного туннеля
```powershell
.\dist\tunnellio.exe status --name prod-api
```

### Остановить один туннель
```powershell
.\dist\tunnellio.exe stop --name prod-api
```

### Прочитать параметры подключения
```powershell
.\dist\tunnellio.exe show-config --name prod-api
```
