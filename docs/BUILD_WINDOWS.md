# Building a Windows binary from source

## Target format
Variant A:
- output: `tunnellio.exe`
- tunnel transport: system `ssh`
- target environment must provide OpenSSH Client

## Runtime behavior of the ready binary
- every managed tunnel gets a runtime name
- if no name is provided, the client generates one automatically
- runtime names are shown in `status`
- tunnels can be stopped by name
- runtime config / connection params can be read back by name

## Build command
```powershell
.\scripts\build_windows_binary.ps1
```

## What goes into the Windows build output
- `dist\tunnellio.exe`
- `artifacts\tunnellio-windows-x64-v<version>\` — local Windows staging folder only

## Important packaging rule
The Windows binary is a standalone artifact.
It is **not** embedded into the universal source archive.

## Universal source archive
Build separately with:
```powershell
.\scripts\build_release_archive.ps1
```

This produces:
- `artifacts\tunnellio-source-v<version>.zip`

That archive is platform-neutral and contains the Python project files, not the Windows binary.

## Recommended runtime commands
### Seed default config and launch a named tunnel
```powershell
.\dist\tunnellio.exe --token YOUR_TOKEN connect --domain existing:mcp --local-port 3000 --run --watch --name prod-api
```

### Re-launch from saved default config
```powershell
.\dist\tunnellio.exe
```

### List tunnel names
```powershell
.\dist\tunnellio.exe status
```

### Check one tunnel by name
```powershell
.\dist\tunnellio.exe status --name prod-api
```

### Stop one tunnel by name
```powershell
.\dist\tunnellio.exe stop --name prod-api
```

### Read runtime config by name
```powershell
.\dist\tunnellio.exe show-config --name prod-api
```
