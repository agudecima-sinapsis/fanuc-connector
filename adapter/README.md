# Adapters

This tree is here so a Pi can `git clone` this public repo and install the
Siemens SHDR adapter without pulling `project-factory-flow-machines`. It is not
coupled to the Fanuc FOCAS adapter (`fanuc/`).

The Python process speaks S7 to the CNC and **serves SHDR pipes on :7878**.
Ingest (same pattern as Okuma/Mitsubishi) connects to that port and maps keys.
cppagent is not part of this path. The compile helper lives in
`adapter/cppagent/install-cppagent.sh` if you need HTTP `/current` later;
Siemens install does not run it.

On the Pi:

```bash
cd adapter/siemens
cp adapter.env.example adapter.env   # set IP_MACHINE
sudo ./install-systemd.sh
```

| Brand / control | Location |
|-----------------|----------|
| Siemens (SINUMERIK 840D sl) | `adapter/siemens/` |
| Fanuc | `fanuc/` (this repo, unchanged) |
