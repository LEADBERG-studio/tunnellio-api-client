# Release packaging guide

## Goal
Produce a downloadable zip archive containing:
- `tunnellio.exe`
- `config.example.json`
- top-level README
- local e2e docs and scripts
- full `docs/` folder

The final user should be able to unpack the release and run the binary directly without Python.

## Step 1: build binary and stage folder
```powershell
.\scripts\build_windows_binary.ps1
```

## Step 2: pack archive
```powershell
.\scripts\build_release_archive.ps1
```

## Output
- staged folder: `artifacts\tunnellio-windows-x64-v<version>\`
- archive: `artifacts\tunnellio-windows-x64-v<version>.zip`

## What goes into the downloadable package
- `tunnellio.exe`
- `config.example.json`
- `README.md`
- `LOCAL_E2E_TESTS.md`
- `run_local_e2e.ps1`
- `docs\*`

## Recommended release notes
Document these ready-binary commands for end users:
```powershell
.\tunnellio.exe --token YOUR_TOKEN connect --domain existing:mcp --local-port 3000 --run --watch --name prod-api
.\tunnellio.exe
.\tunnellio.exe --config .\configs\prod-api.json --config-overwrite yes --token YOUR_TOKEN connect --domain existing:mcp --local-port 3000 --run --watch --name prod-api
.\tunnellio.exe status
.\tunnellio.exe stop --all
```

## Target-machine requirement
The package is Variant A, so it expects system OpenSSH to be installed on the destination machine.
