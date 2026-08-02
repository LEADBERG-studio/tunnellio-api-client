# Changelog

## 0.5.0
- Added TCP bridge password support (`tcpBridgePassword`, `passwordRequired`, `clientProtocol`)
- Added `--tcp-bridge-password` CLI flag for `plan`, `connect`, and `bridge` commands
- Added `TcpBridgeClientProtocol` model with `hello` template from server
- Added `passwordRequired` and `clientProtocol` fields to `TcpBridgeProfile`
- Added `tcpBridgePassword` field to `DomainSummary`
- Updated `bridge.py` to send native Tunnellio wire format (`{"type":"hello","hostname":"...","password":"..."}`) when `clientProtocol.hello` is provided
- Updated `bridge.py` to send `{"type":"accept","connectionId":"...","password":"..."}` for connection accept
- Updated `cli.py` to pass `hello_template`, `password`, `password_required` to `launch_bridge()`
- Updated `planner.py` to pass `tcpBridgePassword` in launch-spec domain block and keyless bridge payload
- Updated config template and config example with `tcpBridgePassword` field
- Added tests for password flow, hello template, and CLI flag parsing
- Backward compatible: bore-protocol mode still works when `clientProtocol` is absent

## 0.4.0
- Implemented native TCP bridge client in pure Python (`tunnellio/bridge.py`) — no external binaries needed
- Wire protocol: null-delimited JSON frames, bore-compatible control handshake, HMAC-SHA256 auth
- `cli.py` now runs the bridge natively via `launch_bridge()` instead of `subprocess.Popen` for tcp_bridge transport
- `TcpBridgeProcess` provides the same `pid`/`poll`/`terminate`/`kill`/`wait` interface as `subprocess.Popen`
- Bidirectional TCP copy via `select` for connection forwarding
- Client is now fully self-sufficient on Windows, Linux, and macOS — only Python 3.11+ required
- Added `tests/test_bridge.py` with fake control server, auth, and forwarding tests
- Updated build script to include bridge tests

## 0.3.0
- Added `bridge` CLI command for one-shot keyless TCP bridge tunnels — no API token, no SSH key required
- Added public keyless endpoint `POST /v1/tcp-bridge/launch` (no Bearer auth) in ApiClient
- Added `Planner.build_keyless_bridge_plan()` that skips meta/capabilities/launch-spec and calls the public endpoint directly
- Added `requiresApiToken` field to `ConnectionProfile` and `TcpBridgeProfile`
- Added `is_tokenless` property to `ConnectionProfile`
- Made `PlanResult.meta` and `PlanResult.domain` optional (None for keyless bridge flow)
- Made `bridge` command exempt from the API token requirement
- Updated config template with `bridge` section
- Updated output writer to handle None meta/domain in plan display
- Added tests for keyless bridge plan flow and bridge CLI parser

## 0.2.0
- Added TCP bridge transport (`connectionMode = tcp_bridge`) as a keyless alternative to reverse SSH
- Added `--transport` CLI flag (`ssh`, `tcp-bridge`, `auto`) for explicit transport selection
- Added automatic fallback from SSH to TCP bridge when `--transport auto` is used and SSH fails quickly
- Added `TcpBridgeProfile`, `TcpBridgeMeta`, `TcpBridgeCapabilities`, and `TcpBridgePortRange` data models
- Made `ConnectionProfile` SSH fields optional — `sshHost`, `sshPort`, `sshUser`, `sshCommand`, `sshArgs`, `sshConfigSnippet` are now all nullable
- Made `PlanResult.key` optional — keyless tcp_bridge flows no longer return a key object
- Added `requiresSshKey` parsing on `ConnectionProfile` and TCP bridge models
- Added `supportedConnectionModes`, `supportsKeylessTcpBridge`, and `tcpBridge` block parsing on `DomainCapabilities`
- Added `tcpBridge` block parsing on `Meta`
- Updated runtime status snapshots and `show-config` output to include `transport`, `effectiveTransport`, and `tcpBridge` data
- Updated `status` command to display the active transport per tunnel
- Updated plan/exec output to be transport-aware (SSH vs TCP bridge)
- Updated session open payload to omit `keyId` when the flow is keyless
- Updated config template with `transport` field for both `plan` and `connect` sections
- Added tests for tcp_bridge keyless flow, transport flag parsing, and config override mapping
- Updated build script with new tcp_bridge test invocations

## 0.1.7
- Aligned the client with the new discovery, auth, and session contract
- Added OAuth discovery helpers, protected-resource metadata loading, PKCE utilities, and extended session-aware planning/runtime metadata
- Added live-validated session lifecycle handling with resume-token aware heartbeat, resume, and close calls
- Expanded config, runtime snapshots, tests, and docs for the new server contract

## 0.1.5
- Added mandatory runtime names for every managed tunnel
- Added automatic runtime-name generation when name is not provided
- Added status filtering by tunnel name
- Added runtime config snapshot lookup by tunnel name with `show-config`
- Stored per-runtime connection configuration artifacts in the runtime registry
- Expanded docs for named tunnel lifecycle and addressable control

## 0.1.4
- Added config-first launch flow for both Python and binary usage
- Added automatically managed default launch config and reusable client configs
- Added overwrite decision flow for explicit client configs: ask / yes / no
- Added full config example file and config documentation
- Added bare binary launch from remembered default config
- Added tests for config resolution and default-config update order

## 0.1.3
- Added local runtime registry for managed tunnel processes
- Added `status` command for listing managed tunnels without requiring an API token
- Added `stop` command for stopping one or all managed tunnels
- Added automatic default runtime status and stop files under `~/.tunnellio/state/runtimes/`
- Expanded docs for user-friendly runtime control and automation

## 0.1.2
- Added supervised tunnel mode with health checks and automatic restart
- Added runtime log-file and status-file support for the ready binary
- Added file-based graceful stop support for supervised runs
- Expanded documentation with ready-binary usage examples and release guidance

## 0.1.1
- Added Windows TLS support via `truststore`
- Added TLS backend diagnostics in client logs
- Updated local e2e runner to probe public URLs with the same TLS backend
- Added binary build scripts for Windows variant A
- Added release archive packaging script
- Added project documentation set for build, testing, operations, releases, and versioning
