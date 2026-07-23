# Release packaging guide

## Goal
Produce a downloadable zip archive containing:
- `tunnellio.exe`
- top-level README
- local e2e docs and scripts
- full `docs/` folder

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

## What should go into the downloadable package
- `tunnellio.exe`
- `README.md`
- `LOCAL_E2E_TESTS.md`
- `run_local_e2e.ps1`
- `docs\*`

## Target-machine requirement
The package is Variant A, so it expects system OpenSSH to be installed on the destination machine.
