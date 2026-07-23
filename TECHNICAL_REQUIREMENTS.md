# API client technical requirements

## Functional requirements

### Authentication
- The helper must accept an API token.
- The helper must send it as `Authorization: Bearer <token>`.
- The helper must fail fast with structured auth errors.

### Key management
- The helper must list server-side keys.
- The helper must optionally generate a local keypair.
- The helper must register the public key with `/api/v1/keys`.
- The helper must keep private keys local.

### Domain management
- The helper must list domains.
- The helper must check hostname availability.
- The helper must create a new domain with a requested lifetime.
- The helper must use an existing domain.
- The helper must request a random ephemeral domain.

### Launch planning
- The helper must call `/api/v1/launch-spec`.
- The helper must expose both the shell command and the argv array.
- The helper must be able to save the returned profile locally.

### Execution
- The helper must be able to:
  - print the plan only;
  - print a human-readable command only;
  - launch the tunnel itself.
- For ephemeral sessions, the helper should call the session-complete endpoint on a graceful shutdown path.

## Non-functional requirements

### Embeddability
- Machine-readable output must be stable.
- JSON mode must write **only JSON** to stdout.
- Logs and diagnostics must go to stderr.

### Reliability
- The helper must never require parsing of human-readable text by the parent program.
- Exit codes must be stable and documented.
- Local state writes must be atomic enough to avoid corrupting profiles.

### Portability
- First target: Linux/macOS shell usage.
- Second target: Windows support with predictable path handling.

## Recommended local state layout

```text
~/.tunnellio/
  config.json
  profiles/
  keys/
  logs/
  state/
```

## Suggested exit codes
- `0` success
- `1` generic runtime failure
- `2` bad input / validation
- `3` auth failure
- `4` API/server failure
- `5` conflict / unavailable resource

## Deferred requirements
- GUI
- billing awareness inside the client
- token issuance
- MFA flows
- team/user switching
