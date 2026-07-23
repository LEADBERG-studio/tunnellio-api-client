# Changelog

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
