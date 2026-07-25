# Integration contract for calling applications

## Why this matters
The client is not only a human-facing CLI.
It is also a local control layer that another application can call.

That is especially important when the tunnel uses:
- a randomly selected domain
- an ephemeral/random hostname
- a generated runtime name

In those cases the calling application cannot assume the final public address in advance.
It must be able to:
1. start the tunnel
2. identify the tunnel instance by name
3. read back the resolved server-side connection data
4. continue managing the same tunnel by that name

## Core guarantees
For every managed tunnel, the client guarantees:
- a runtime name always exists
- the runtime name can be explicit or auto-generated
- runtime status is stored locally
- runtime connection/config snapshot is stored locally
- the same runtime name can be used to:
	- inspect status
	- stop the tunnel
	- fetch runtime config and connection data

## Naming rules
### Explicit runtime name
If the caller passes `--name prod-api`, the tunnel runtime name is `prod-api`.

### Automatic runtime name
If the caller does not pass `--name`, the client generates one automatically.

The generated name is still a first-class identifier.
The caller should treat it exactly like a user-supplied name.

## What the calling application should do
## Recommended flow for machine callers
### Step 1: start the tunnel
Example:
```powershell
.\tunnellio.exe --token YOUR_TOKEN connect --domain random --key existing:mcp --local-port 3000 --run --watch
```

If the caller wants a stable identifier, it should prefer passing an explicit name:
```powershell
.\tunnellio.exe --token YOUR_TOKEN connect --domain random --key existing:mcp --local-port 3000 --run --watch --name app-backend
```

### Step 2: discover the runtime name if it was auto-generated
The caller can read it from:
- process stdout/stderr conventions during launch
- `status`
- runtime registry files

For predictable automation, it is strongly recommended to pass `--name` explicitly.

### Step 3: query status by name
```powershell
.\tunnellio.exe status --name app-backend
```

This returns the runtime entry for that specific tunnel.

### Step 4: fetch resolved connection data by name
```powershell
.\tunnellio.exe show-config --name app-backend
```

This returns a JSON snapshot containing:
- runtime metadata
- launchConfig
- connection
- saved status/stop file paths
- auth contract fields (`authMode`, discovery URL, protected-resource metadata URL, token/authorize/introspection URLs, token verification mode, supported scopes, supported bearer methods)
- session/runtime identifiers (`sessionId`, `resumeToken`, `proxySessionId`, runtime name)

The caller should treat the returned auth/runtime contract as authoritative.
If the caller requested a mode but the server negotiated a different final mode, the returned contract is the truth the caller must follow.

## Critical random-domain scenario
When the caller starts a tunnel with a random or ephemeral domain, the client may receive a server-chosen hostname.
The caller must not rely only on the original CLI arguments, because those arguments do not fully describe the final server-side binding.

Instead, after launch, the caller should query the tunnel by runtime name and read back the returned connection data.

At minimum, the caller can obtain:
- resolved domain / hostname
- public URL
- SSH connection parameters

That is exactly why `show-config --name <runtime>` exists.

## Console behavior vs programmatic behavior
### Interactive console usage
When a human runs:
```powershell
.\tunnellio.exe show-config --name prod-api
```

the JSON snapshot is printed to stdout in the console.

### Programmatic usage
When another application runs the same command, the contract is:
- success: JSON in `stdout`, exit code `0`
- failure: error message, non-zero exit code

That means the caller can simply spawn the process and parse stdout as JSON.

## Local runtime registry
Each managed tunnel creates local artifacts in:
- `~/.tunnellio/state/runtimes/<name>.json`
- `~/.tunnellio/state/runtimes/<name>.config.json`
- `~/.tunnellio/state/runtimes/<name>.stop`

### `<name>.json`
Contains runtime status information, such as:
- `name`
- `state`
- `pid`
- `publicUrl`
- `healthUrl`
- `sessionId`
- `sessionStatus`
- `resumeToken`
- `proxySessionId`
- `routeState`
- `lastHeartbeatAt`
- `runtimeConfigFile`
- `stopFile`
- `updatedAt`

### `<name>.config.json`
Contains the runtime snapshot used for addressable integration.
This is the main source for machine consumers that need connection information after launch.

It includes:
- `runtimeName`
- `savedAt`
- `statusFile`
- `stopFile`
- `launchConfig`
- `connection`

### `<name>.stop`
Used for graceful stop signaling.

## Operational commands for machine callers
### Start remembered default tunnel
```powershell
.\tunnellio.exe
```

### List tunnels
```powershell
.\tunnellio.exe status
```

### Get one tunnel status by name
```powershell
.\tunnellio.exe status --name app-backend
```

### Get connection snapshot by name
```powershell
.\tunnellio.exe show-config --name app-backend
```

### Stop one tunnel by name
```powershell
.\tunnellio.exe stop --name app-backend
```

### Stop all managed tunnels
```powershell
.\tunnellio.exe stop --all
```

## Recommendation for integrators
If another application is the caller, the safest pattern is:
1. always provide `--name`
2. start the tunnel
3. immediately call `show-config --name <name>`
4. persist the returned domain/public URL if needed
5. use the same name later for status and stop

This makes random-domain and ephemeral-domain flows deterministic from the caller's perspective.
