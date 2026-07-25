# Operations guide

## Raw SSH vs client
Raw SSH only launches a reverse tunnel.
The client adds:
- API discovery
- capability-aware planning
- key/domain/session orchestration
- Windows-native TLS validation via `truststore`
- structured logs
- runtime registry
- status output
- optional SSH execution via `connect --run`
- supervised restart mode via `connect --run --watch`
- stop/list commands for managed runtimes
- runtime names for addressable control
- runtime config snapshots retrievable by name
- config-first launch model
- ephemeral session completion
- session lifecycle management: open, heartbeat, resume, close
- resume-token aware session maintenance for heartbeat/close/resume calls

## Transport model
The actual tunnel is still created by system `ssh` with reverse forwarding.
The client does not replace SSH transport.

## Runtime names
Every managed tunnel has a name.

- If `--name` is provided, it is used.
- If `--name` is omitted, the client generates a stable runtime name for that launch.

That name is then shown in the runtime registry and used for:
- `status --name`
- `stop --name`
- `show-config --name`

## Why this is operationally necessary
Addressable control is not only a convenience feature.
It is required when:
- more than one tunnel exists on the same machine
- the tunnel is launched by another application
- the domain is random or ephemeral
- the caller needs to know the final server-side hostname after launch

In those cases, runtime name becomes the stable local identifier, and `show-config --name` becomes the handoff mechanism between the client and the calling application.

## Recommended production run
### Seed remembered defaults
```powershell
.\tunnellio.exe --token YOUR_TOKEN connect --domain existing:mcp --local-port 3000 --run --watch --name prod-api --health-path / --log-file .\logs\tunnel.log
```

### Re-launch from remembered config
```powershell
.\tunnellio.exe
```

### See all runtime names
```powershell
.\tunnellio.exe status
```

### See one runtime by name
```powershell
.\tunnellio.exe status --name prod-api
```

### Stop one runtime by name
```powershell
.\tunnellio.exe stop --name prod-api
```

### Get runtime config / connection params by name
```powershell
.\tunnellio.exe show-config --name prod-api
```

## Runtime registry
Even if you do not pass `--status-file` or `--stop-file`, the client creates managed runtime files automatically in:
- `~/.tunnellio/state/runtimes/*.json`
- `~/.tunnellio/state/runtimes/*.config.json`
- `~/.tunnellio/state/runtimes/*.stop`

This gives you a stable local registry of running and recently used tunnel instances.
