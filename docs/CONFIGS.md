# Configuration model

## Goal
The client can now run from either:
- the automatically managed **default config**
- an explicitly chosen **client config**

Important launch order:
1. resolve the target config
2. if CLI flags change config values, decide whether to rewrite the config
3. build the final config snapshot
4. run from that config snapshot

## Tunnel names
Every managed tunnel has a name.

- explicit name: set `connect.name` in config or pass `--name`
- implicit name: generated automatically if missing

That runtime name is then used for:
- tunnel listing
- status lookup
- addressable stop
- runtime config lookup
- machine retrieval of server-side connection data after launch

## Why runtime config lookup matters
For static domains, the calling application often already knows the intended hostname.
For random or ephemeral domains, this is not true.

In those flows, the caller must be able to launch the tunnel first and then read back the final server-side connection data.
That is why the client stores runtime snapshots and exposes them by runtime name.

The practical rule is:
- launch by config or CLI
- identify the tunnel by runtime name
- read back the final connection data with `show-config --name <name>`

## Config files
### Project example
- `config.example.json`

This file documents every supported field.

### Default config
- `~/.tunnellio/default-launch.json`

Behavior:
- if no explicit `--config` is passed, this config is selected automatically
- if CLI flags are passed, the client updates this file first
- then the client launches from the updated file
- if the file already contains saved values and no new CLI overrides are given, running the binary with no args uses this config directly

### Client configs
Recommended directory:
- `~/.tunnellio/configs/`

You may also keep client configs anywhere else and pass them by explicit path.

## Precedence and overwrite rules
### No explicit config
If `--config` is not passed:
- the default config is the target
- CLI flags overwrite the default config automatically
- launch then proceeds from the rewritten default config

### Explicit config with CLI flags
If `--config path.json` is passed and CLI flags also provide values:
- if the config does not exist, it is created and launch proceeds from it
- if the config exists and would change, the client asks whether to overwrite it
- `--config-overwrite yes` skips the question and rewrites the file
- `--config-overwrite no` keeps the file unchanged, but CLI values override matching config values for this run only

## Runtime control by name
### List all tunnels
```powershell
.\tunnellio.exe status
```

### Show one tunnel status by name
```powershell
.\tunnellio.exe status --name prod-api
```

### Stop one tunnel by name
```powershell
.\tunnellio.exe stop --name prod-api
```

### Read the saved runtime config / connection params by name
```powershell
.\tunnellio.exe show-config --name prod-api
```

## Runtime registry artifacts
- `~/.tunnellio/state/runtimes/<name>.json` — runtime status
- `~/.tunnellio/state/runtimes/<name>.config.json` — runtime config snapshot with connection data
- `~/.tunnellio/state/runtimes/<name>.stop` — graceful stop signal
