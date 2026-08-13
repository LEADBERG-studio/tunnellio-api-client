# Tunnellio v0.6.1

## Summary
- The TCP bridge actually raises a tunnel now. A configured domain on a registered account could not be published at all, and a random one only appeared to work because nothing ever asked it for a request. Six separate faults were in place at the same time, and each one alone was enough to keep the tunnel down.

## Highlights
- **A configured domain works, with a token and with a registration alone.** `POST /v1/sessions/open` no longer demands `keyId`. There is no SSH in the bridge, so there is no key to name. Six sources already said `requiresSshKey: false`; the seventh, the validator, said otherwise and won.
- **The owner key of the hostname.** It ships with the address in `connectionProfile.tcpBridge.token` and travels in the `hello` frame. Before this, anyone who knew a subdomain took over a live tunnel: the server closed the previous session as `replaced` and asked nothing.
- **The handshake completes.** The server now returns the public port in its `hello`, so the client stops treating a successful login as a failure.
- **The tunnel stays up.** Silence in the control channel is no longer read as a disconnect, and the client sends its own heartbeat every fifteen seconds so a home router does not quietly forget the mapping overnight.
- **OAuth over the bridge is refused honestly.** The bridge passes bytes straight through, so a token cannot be checked anywhere. Such a domain used to look protected in the console while being open to the whole internet.

## What works with what

| Situation | Address | Bridge | Cost |
| --- | --- | --- | --- |
| No account, no credentials | random `tmp-xxxxxxxx`, 24 h | works | free |
| Registered, domain configured for the bridge | your own permanent subdomain | works | free |
| Bridge password on the domain | your own subdomain, password required | works | Pro |
| Integration API (token), configured or random address | any | works | Pro |

- A permanent subdomain still requires a registered account: it is a name held in our domain for years, and someone has to stand behind it. A random address lives 24 hours and dies on its own.
- The Free plan allows up to 10 domains. Extra ones are marked `plan_limited`.
- `authMode: oauth` and `dual` are incompatible with `connectionMode: tcp_bridge` and `auto`. Use Cloud proxy for OAuth, or Legacy for the bridge.

```powershell
# No credentials at all, random address
.\tunnellio.exe connect --transport tcp-bridge --domain random --local-port 8787 --run

# Registered account, configured domain, no SSH key anywhere
.\tunnellio.exe --token <TOKEN> connect --domain existing:tuntun ^
  --local-host 127.0.0.1 --local-port 8787 --transport tcp-bridge --run --watch --name myvpn-files

# Domain protected by a bridge password (Pro)
.\tunnellio.exe --token <TOKEN> connect --domain existing:demo ^
  --tcp-bridge-password <PASSWORD> --local-port 8787 --transport tcp-bridge --run
```

## Changelog
- The owner key of the hostname is sent in the `hello` frame; it arrives in the connection profile together with the address and proves the right to publish under that name.
- The key is sent whenever the server provides one, not only when the server demands one, so a soft server still learns who it is talking to.
- The bridge password is no longer taken from the session token. They are different things, and substituting one for the other guaranteed `invalid_bridge_password` on every password-protected domain.
- The challenge handshake is skipped for the native protocol. Our bridge never sends `Challenge`, so every connection waited for it until the timeout, which looked like a tunnel that came up and then ignored requests.
- Silence in the control channel is no longer mistaken for a disconnect. The client waited half a second while the server sends a heartbeat every thirty, so the bridge died half a second after a successful handshake.
- The client sends its own heartbeat every fifteen seconds. Nothing requires it, but a home router forgets an idle mapping without saying a word, and a tunnel that stood overnight led nowhere by morning.
- A missing public port is no longer a failed handshake: the HTTP bridge publishes by name and may not report a port at all.
- The connection id is sent under both names, `id` and `connectionId`. The server reads the first, we sent the second, and every connection ended in `connection_not_found`.
- Frame limit raised to 8192 bytes, matching the server. 256 was enough until the greeting grew an address and a port, and then the frame was cut mid-JSON.
- `.well-known/oauth-protected-resource` is no longer requested from the public address on legacy or bridge domains. Someone else's program answers there; it returns 404, and the 404 landed in the log as an error.
- `Runtime name:` is printed once. The second, empty line is gone.
- `docs/TCP_BRIDGE.md` brought in line with the wire protocol as it actually is, including the owner key, the refusal codes and the OAuth limitation.

### Server side, for reference (repository `tunnellio`)
- `POST /v1/sessions/open` accepts a request with no `keyId` when the domain mode is `tcp_bridge` or `auto`; an explicitly invalid `keyId` such as `-5` is still a `validation_error`, and Direct SSH without a key is still impossible.
- A keyless session no longer wipes the key already configured on the domain.
- `heartbeat`, `resume` and `close` verified on a keyless session; they never required a key.
- The bridge rejects an unknown hostname (`unknown_hostname`), a wrong owner key (`invalid_bridge_key`, always) and an unreachable database (`bridge_unavailable`) instead of admitting everyone. A client with no key at all is governed by `TCP_BRIDGE_OWNER_KEY_REQUIRED`; while it is `0` such a client passes and is recorded as `bridge.legacy`.
- The server `hello` carries the public port, the public URL and the heartbeat interval.
- `oauth_requires_proxy` refuses the bridge plus OAuth combination at domain creation and at session open.
- The session payload names its `keyId`, including its absence.

## Artifacts
- `tunnellio.exe`
- `tunnellio-windows-x64-v0.6.1.zip`
- `tunnellio-source-v0.6.1.zip`

## Verification
- Tests: 91 pass in the client, 154 in the server.
- Live-checked end to end with real sockets, not mocks: a real bridge control port, a real public port, a real local service and a request from the outside. A configured domain plus a token opened a session with no key, the request reached the local service and came back, a heartbeat did not kill the session, and a foreign owner key was rejected with `invalid_bridge_key`. The check is committed as `tests/live_bridge_check.py` in the server repository, because the unit tests of both halves were green while the halves did not work together.

## Upgrade notes
- Deploy the server first: the client sends the owner key, and only a fixed server knows what to do with it.
- Once the new client has spread, set `TCP_BRIDGE_OWNER_KEY_REQUIRED=1` on the server. Until then older clients still connect and are listed in the journal as `bridge.legacy`, which is how you see who is left to update.
- Existing configs, commands and flags are unchanged.

## Notes for GitHub publication
- Upload the binary and both zips from this release subfolder.
- Recheck that the changelog matches `CHANGELOG.md` for the target version.
