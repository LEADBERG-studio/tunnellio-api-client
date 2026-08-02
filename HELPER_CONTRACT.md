# Helper contract for embedded usage

## Modes

### 1. Interactive human mode
Example:
```bash
tunnellio connect
```
- asks questions in the terminal;
- prints a friendly summary;
- can optionally start the tunnel.

### 2. Machine-readable plan mode
Example:
```bash
tunnellio plan --output json --domain random --key existing:work-laptop --local-port 3000
```
- does not require parsing human-readable output;
- returns a JSON object with the selected key, domain and launch spec;
- does not launch the tunnel.

### 3. Exec mode
Example:
```bash
tunnellio connect --domain random --key existing:work-laptop --local-port 3000 --run
```
- creates the plan;
- launches SSH;
- returns process/session metadata.

## Stdout/stderr contract

### JSON mode
- `stdout`: only JSON
- `stderr`: diagnostics/logging only

### Human mode
- `stdout`: user-facing text
- `stderr`: warnings/errors

## Minimum JSON result schema

### SSH reverse tunnel
```json
{
  "ok": true,
  "mode": "plan",
  "key": {
    "id": 1,
    "name": "work-laptop",
    "fingerprint": "SHA256:..."
  },
  "domain": {
    "id": 2,
    "hostname": "mcp-dev",
    "fqdn": "mcp-dev.tunnel.example.net",
    "publicUrl": "https://mcp-dev.tunnel.example.net",
    "mode": "persistent"
  },
  "connectionProfile": {
    "sshHost": "tunnel.example.net",
    "sshPort": 2222,
    "sshUser": "tunnel",
    "localHost": "127.0.0.1",
    "localPort": 3000,
    "remoteHostname": "mcp-dev"
  },
  "launch": {
    "command": "ssh ...",
    "args": ["ssh", "-i", "~/.tunnellio/keys/work-laptop", "-N", "..."],
    "transport": "ssh"
  },
  "savedProfile": {
    "name": "mcp-dev",
    "path": "~/.tunnellio/profiles/mcp-dev.json"
  }
}
```

### Keyless TCP bridge
When `connectionMode = tcp_bridge` and `requiresSshKey = false`, the `key` field is omitted
and the `launch` block contains the native bridge command instead of SSH args:
```json
{
  "ok": true,
  "mode": "plan",
  "domain": {
    "id": 3,
    "hostname": "demo-app",
    "fqdn": "demo-app.tunnellio.site",
    "publicUrl": "https://demo-app.tunnellio.site",
    "mode": "persistent",
    "connectionMode": "tcp_bridge"
  },
  "connectionProfile": {
    "connectionMode": "tcp_bridge",
    "requiresSshKey": false,
    "publicUrl": "https://demo-app.tunnellio.site",
    "localHost": "127.0.0.1",
    "localPort": 3000,
    "tcpBridge": {
      "enabled": true,
      "protocol": "bore",
      "authRequired": false,
      "requiresSshKey": false,
      "host": "tunnel.example.net",
      "controlPort": 7835,
      "publicPort": 51000,
      "publicBaseDomain": "tunnel.example.net",
      "hostname": "demo-app",
      "publicUrl": "https://demo-app.tunnellio.site",
      "localHost": "127.0.0.1",
      "localPort": 3000,
      "preconfiguredSubdomain": true,
      "generatedSubdomain": false,
      "token": null,
      "command": "tunnellio-bridge connect --host tunnel.example.net --control-port 7835 --hostname demo-app --local-host 127.0.0.1 --local-port 3000",
      "args": ["tunnellio-bridge", "connect", "--host", "tunnel.example.net", "--control-port", "7835", "--hostname", "demo-app", "--local-host", "127.0.0.1", "--local-port", "3000"]
    }
  },
  "launch": {
    "command": "tunnellio-bridge connect --host tunnel.example.net --control-port 7835 --hostname demo-app --local-host 127.0.0.1 --local-port 3000",
    "args": ["tunnellio-bridge", "connect", "--host", "tunnel.example.net", "--control-port", "7835", "--hostname", "demo-app", "--local-host", "127.0.0.1", "--local-port", "3000"],
    "transport": "tcp_bridge"
  },
  "savedProfile": {
    "name": "demo-app",
    "path": "~/.tunnellio/profiles/demo-app.json"
  }
}
```

The `key` field is absent when the connection is keyless. Callers should check
`connectionProfile.requiresSshKey` / `connectionProfile.tcpBridge.enabled` or
`launch.transport` before assuming SSH.

### Tokenless keyless bridge (`bridge` command)
When using the `bridge` command, no API token is required. The client calls
`POST /v1/tcp-bridge/launch` without Bearer auth. The response omits `meta`,
`key`, `domain`, `capabilities`, `discovery`, and `auth` — only `connectionProfile`
and `launch` are returned:
```json
{
  "ok": true,
  "mode": "bridge",
  "connectionProfile": {
    "connectionMode": "tcp_bridge",
    "requiresSshKey": false,
    "requiresApiToken": false,
    "publicUrl": "https://my-app.tunnellio.site",
    "localHost": "127.0.0.1",
    "localPort": 3000,
    "tcpBridge": { ... }
  },
  "launch": {
    "command": "tunnellio-bridge connect ...",
    "args": ["tunnellio-bridge", "connect", ...],
    "transport": "tcp_bridge"
  }
}
```

## Error contract

Example:
```json
{
  "ok": false,
  "error": {
    "code": "domain_not_available",
    "message": "Hostname is already taken."
  }
}
```

## Input-needed contract for GUI/host integrations
When the helper lacks enough data and is running in non-interactive machine mode, it should return structured missing-input information instead of hanging or printing prompts.

Example:
```json
{
  "ok": false,
  "error": {
    "code": "interactive_input_required",
    "message": "More input is required.",
    "details": {
      "missing": ["domainMode", "keySelection"],
      "choices": {
        "domainMode": ["existing", "new", "random"]
      }
    }
  }
}
```
