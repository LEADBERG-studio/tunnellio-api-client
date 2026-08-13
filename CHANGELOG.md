# Changelog

## 0.6.1

### The TCP bridge actually raises a tunnel

Every piece below was enough on its own to leave `connect --transport tcp-bridge`
dead, and all of them were in place at once. A configured domain on a registered
account could not be published at all; a random one only appeared to work
because nothing ever asked it for a request.

- The owner key of the hostname is sent in the `hello` frame. It arrives in the
  connection profile together with the address and proves the right to publish
  under that name. Before, anyone who knew a subdomain took over a live tunnel:
  the server closed the previous session as `replaced` without asking anything.
- The key is sent whenever the server provides one, not only when the server
  demands one. A soft server still learns who it is talking to.
- The bridge password is no longer taken from the session token. They are
  different things, and substituting one for the other guaranteed
  `invalid_bridge_password` on every password-protected domain.
- The challenge handshake is skipped for the native protocol. Our bridge never
  sends `Challenge`, so every connection sat waiting for it until the timeout,
  which looked like a tunnel that came up and then ignored requests.
- Silence in the control channel is no longer mistaken for a disconnect. We
  waited half a second, the server sends a heartbeat every thirty, so the bridge
  died half a second after a successful handshake.
- The client sends its own heartbeat every fifteen seconds. Nothing requires it,
  but a home router forgets an idle mapping without saying a word, and a tunnel
  that stood overnight led nowhere by morning.
- A missing public port is no longer a failed handshake. The HTTP bridge
  publishes by name; there may be no port number in the answer at all.
- The connection id is sent under both names (`id` and `connectionId`). The
  server reads the first, we sent the second, and every connection ended in
  `connection_not_found`.
- Frame limit raised to 8192 bytes, matching the server. 256 was enough until
  the greeting grew an address and a port, and then the frame was cut mid-JSON.
- `.well-known/oauth-protected-resource` is no longer requested from the public
  address on legacy or bridge domains. There is someone else's program behind
  that address; it answers 404, and the 404 landed in the log as an error.
- `Runtime name:` is printed once. The second, empty line is gone.

## 0.6.0

### Credential-aware connection modes

The API token is now the most capable credential, not a hard prerequisite. What
works with what:

| Credentials | Available modes |
| --- | --- |
| API token | everything: full API flow, SSH stable, TCP stable, TCP random |
| SSH key only | `ssh_stable`, `tcp_stable`, `tcp_random` |
| nothing | `tcp_stable`, `tcp_random` |

In those last three modes the API token is never read and never validated, even
if one happens to be configured.

- Added `tunnellio/modes.py`: the credential matrix, `resolve_mode()`,
  `available_modes()`, `requires_api_token()`, `requires_ssh_key()`.
- `connect` no longer demands a token up front. The requirement is derived from
  the mode the launch actually resolves to.
- Added `Planner.build_offline_ssh_plan()`: a direct SSH reverse forward to a
  reserved domain, built locally with no API call at all. A reserved domain plus
  its bound key already contains everything needed to connect.
- `connect` routes to the keyless bridge endpoint automatically for
  `tcp_stable` / `tcp_random` when no token is configured.
- Operations that genuinely use the API (creating a domain or key, cloud proxy,
  OAuth, `auto` transport) still require a token, unchanged.

### Plan limits are no longer reported as auth failures

- Added `PlanRequiredError`. Previously any HTTP 403 became `AuthError`, so a
  free account hitting `403 plan_required` on `POST /v1/meta` looked like a bad
  credential and aborted the whole `connect`. This is the bug that forced
  integrators to bypass the CLI entirely.
- Added `PLAN_REQUIRED_CODES` and `is_plan_limit()`. A plain `forbidden` with no
  plan wording is still an `AuthError`.
- `POST /v1/meta` and `POST /v1/capabilities` are now advisory. A plan refusal
  degrades gracefully instead of aborting.
- Added `Capabilities.known` and `Capabilities.unknown()`. When the server does
  not describe its capabilities, the client stops second-guessing it: the server
  remains the source of truth and rejects anything it does not allow.
- Capability gates (random ephemeral, domain/key creation, lifetime ranges) are
  skipped when capabilities are unknown, and still enforced when they are known.
- Added `PlanResult.degraded`, surfaced as `degraded` in JSON output, so callers
  can see exactly which advisory data was unavailable.
- The `meta` command now states plainly that the token is valid and the plan is
  the limit.

### Fixes

- `bridge --save-profile` always crashed: `_save_profile()` called
  `meta.to_dict()`, but the keyless bridge path passes `meta=None` by design.
  Meta is now written only when present.
- `meta` is optional throughout the planner: `_load_discovery`,
  `_load_protected_resource`, `build_auth_contract` and `_save_profile`.

### Tests

- New `tests/test_errors.py`: plan-limit versus auth-failure matrix.
- New `tests/test_modes.py`: the credential matrix, mode resolution and the
  offline SSH plan.
- New plan-limit cases in `tests/test_planner.py`.
- 91 tests pass across errors, modes, planner, cli, client, bridge, config and
  oauth.

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
