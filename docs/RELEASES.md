# Release packaging guide

## Goal
Prepare two different release artifacts:
- standalone Windows binary: `tunnellio.exe`
- universal source archive: `tunnellio-source-v<version>.zip`

The binary is Windows-specific.
The source archive is platform-neutral and contains the Python project files.

## Step 1: build Windows binary
```powershell
.\scripts\build_windows_binary.ps1
```

## Step 2: build universal source archive
```powershell
.\scripts\build_release_archive.ps1
```

## Output
- Windows stage folder: `artifacts\tunnellio-windows-x64-v<version>\`
- universal source archive: `artifacts\tunnellio-source-v<version>.zip`

## What goes into the source archive
- project source under `src/`
- helper scripts
- docs
- tests
- config example
- project metadata files

The Windows binary does **not** go into the source archive.

## What goes into the prepared local release folder
- `tunnellio.exe`
- `tunnellio-source-v<version>.zip`
- `GITHUB_RELEASE.md`

## Recommended release notes
Document that:
- `tunnellio.exe` is the ready Windows binary
- `tunnellio-source-v<version>.zip` is the universal Python/source package
- the source archive can be used outside Windows, subject to Python/OpenSSH/runtime requirements
