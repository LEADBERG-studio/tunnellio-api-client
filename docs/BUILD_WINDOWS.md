# Building a Windows binary from source

## Target format
Variant A:
- output: `tunnellio.exe`
- tunnel transport: system `ssh`
- target environment must provide OpenSSH Client

## Prerequisites
- Windows x64
- Python 3.11+
- `python` in PATH
- OpenSSH Client in PATH

Check SSH:
```powershell
ssh -V
ssh-keygen -V
```

## One-time setup
```powershell
python -m pip install -e .
python -m pip install -r requirements-build.txt
```

## Build command
```powershell
.\scripts\build_windows_binary.ps1
```

## What the build script does
1. installs package dependencies
2. installs build dependencies
3. runs local compile/test checks unless `-SkipTests` is passed
4. builds `dist\tunnellio.exe` via PyInstaller
5. creates a staged release directory under `artifacts\tunnellio-windows-x64-v<version>`
6. copies binary + docs + test runner files into that staged directory

## Optional flags
```powershell
.\scripts\build_windows_binary.ps1 -Clean
.\scripts\build_windows_binary.ps1 -SkipTests
.\scripts\build_windows_binary.ps1 -Version 0.1.1
```

## Files produced
- `dist\tunnellio.exe`
- `artifacts\tunnellio-windows-x64-v<version>\`

## Create downloadable archive
```powershell
.\scripts\build_release_archive.ps1
```

This creates:
- `artifacts\tunnellio-windows-x64-v<version>.zip`

## Smoke test built binary
```powershell
.\dist\tunnellio.exe --token YOUR_TOKEN --verbose meta
```

## Production note
The binary does not embed SSH. The target machine still needs system OpenSSH.
