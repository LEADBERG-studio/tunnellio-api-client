# Release packaging guide

## Goal
Prepare two different release artifacts:
- standalone Windows binary: `tunnellio.exe`
- universal source archive: `tunnellio-source-v<version>.zip`

The binary is Windows-specific.
The source archive is platform-neutral and contains the Python project files.

## Source archive rule
The universal source archive must be built from the **git-tracked project state**, not from a hand-maintained local file list.

That means:
- the archive should reflect a specific git ref
- the archive content should match what is actually versioned
- local untracked files must not leak into the source release

## Step 1: build Windows binary
```powershell
.\scripts\build_windows_binary.ps1
```

## Step 2: build universal source archive from git
```powershell
.\scripts\build_release_archive.ps1
```

Optional explicit ref:
```powershell
.\scripts\build_release_archive.ps1 -Ref HEAD
.\scripts\build_release_archive.ps1 -Ref v0.1.5
```

## Output
- Windows stage folder: `artifacts\tunnellio-windows-x64-v<version>\`
- universal source archive: `artifacts\tunnellio-source-v<version>.zip`

## How the source archive is built
The script now uses git state rather than a manual include list.
By default it archives `HEAD`.

This makes the source archive align with the repository revision that is actually being released.

## What goes into the source archive
Everything that is tracked in git at the chosen ref and belongs to that revision.

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
