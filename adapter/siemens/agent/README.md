# Siemens MTConnect agent

cppagent config for the Siemens SHDR adapter. The C++ tree is **not** vendored
here: build or extract the binary from `tools/cppagent` (native install:
`unix/README.md` → `/usr/local/bin/agent`; Pi fallback: docker `linux/arm64`).

| Setting | Value |
|---------|--------|
| Schema | 1.3 (`PROGRAM_COMPLETED` / `PROGRAM_OPTIONAL_STOP` validate here) |
| HTTP | `:5000` (`/probe`, `/current`) |
| Adapter | device `siemens` at `127.0.0.1:7878` |
| ReconnectInterval | 1000 ms |

Stable DataItem `name` attributes (SHDR keys): `avail`, `program`, `mode`,
`execution`, `alarm`. When `PROGRAM_DB` is unset the adapter omits the SHDR
`program` key and the agent reports Program as unavailable.

Execution is ProductionTracker-ready at this agent: `ACTIVE`,
`PROGRAM_COMPLETED`, `PROGRAM_STOPPED` (plus `INTERRUPTED`, `READY`,
`PROGRAM_OPTIONAL_STOP` from the 840D sl map). Later ingest must map 1:1.

Run (after `/usr/local/bin/agent` is on the PATH):

```bash
/usr/local/bin/agent run "$(dirname "$0")/agent.cfg"
curl http://127.0.0.1:5000/current
```
