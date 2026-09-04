# Adapters

This tree is here so a Pi can `git clone` this public repo and install the
Siemens agent without pulling `project-factory-flow-machines`. It is not
coupled to the Fanuc FOCAS adapter (`fanuc/`).

On the Pi:

```bash
cd adapter/siemens
cp adapter.env.example adapter.env   # set IP_MACHINE
sudo ./install-systemd.sh
```

The first run calls `install-cppagent.sh` if `/usr/local/bin/agent` is missing.
That compiles cppagent (30–90+ min on a Pi). Later runs skip the compile.

| Brand / control | Location |
|-----------------|----------|
| Siemens (SINUMERIK 840D sl) | `adapter/siemens/` |
| Fanuc | `fanuc/` (this repo, unchanged) |
