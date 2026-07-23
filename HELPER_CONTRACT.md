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
    "args": ["ssh", "-i", "~/.tunnellio/keys/work-laptop", "-N", "..."]
  },
  "savedProfile": {
    "name": "mcp-dev",
    "path": "~/.tunnellio/profiles/mcp-dev.json"
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
