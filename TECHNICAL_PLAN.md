# API client technical plan

## Goal
Create a separate client/helper repository for Tunnellio that can be used in three ways:

1. **Interactive CLI** for people in a terminal.
2. **Machine-readable plan tool** for other software.
3. **Launcher** that can optionally start and stop the SSH tunnel itself.

## Core responsibilities

### 1. Token-based API access
- Read API token from env, config file or explicit flag.
- Never manage token issuance or revocation; that remains on the web UI side.

### 2. Local SSH key handling
- Generate local keypairs.
- Register public keys with `/api/v1/keys`.
- Store private keys under `~/.tunnellio/keys/` by default.

### 3. Domain workflows
Support three domain modes:
- existing
- new
- random ephemeral

### 4. Launch planning
Use `/api/v1/launch-spec` to create a machine-readable execution plan.

### 5. Optional execution
- Run SSH in foreground or background.
- Persist local profiles for re-use.
- Call `POST /api/v1/sessions/{sessionId}/complete` on normal teardown for ephemeral sessions.

## Proposed repository layout

```text
client/
  README.md
  pyproject.toml or package.json
  src/
    cli entrypoint
    config/state/profile modules
    api client module
    ssh process module
  tests/
  docs/
```

## Recommended development phases

### Phase 1 — API integration only
- bearer token config
- metadata/capabilities fetch
- list/create keys
- list/create/check/delete domains
- launch-spec retrieval
- JSON output mode

### Phase 2 — local key and profile support
- local key generation
- profile persistence
- profile reuse
- `up/down/status/list`

### Phase 3 — embedded/SDK ergonomics
- stable JSON schemas
- clear exit codes
- helper library API
- process handle reporting

## Success criteria
The client is successful when another application can do this reliably:
1. call the helper with a token and minimal options;
2. receive a JSON launch plan;
3. optionally execute `sshArgs` without parsing human-readable text;
4. clean up ephemeral sessions on shutdown.
