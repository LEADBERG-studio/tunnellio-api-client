# Changelog

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
