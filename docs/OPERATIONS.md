# Operations guide

## How the client differs from raw SSH
Raw SSH only launches a reverse tunnel.
The client adds:
- API discovery
- capability-aware planning
- key/domain/session orchestration
- Windows-native TLS validation via `truststore`
- structured logs
- optional SSH execution via `connect --run`
- ephemeral session completion

## Transport model
The actual tunnel is still created by system `ssh` with reverse forwarding.
The client does not replace SSH transport.

## Production supervision
Recommended wrappers:
- Windows: NSSM, WinSW, Task Scheduler
- Linux: systemd

## Health strategy
You should monitor two things:
1. SSH process state
2. public URL / health endpoint reachability

A healthy process does not always mean a healthy route.

## Useful SSH options
- `ServerAliveInterval=30`
- `ServerAliveCountMax=3`
- `ExitOnForwardFailure=yes`
- `StrictHostKeyChecking=accept-new`

## Recommended production pattern
1. use client planning/logging
2. run tunnel under an external supervisor
3. probe a public health endpoint
4. restart on repeated health failures

## Windows TLS
On Windows the client uses `windows-truststore` instead of the problematic raw OpenSSL validation path.
Verbose logs show the active backend.
