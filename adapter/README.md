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

cppagent still needs to be on the box (`AGENT_BIN`, default `/usr/local/bin/agent`).

| Brand / control | Location |
|-----------------|----------|
| Siemens (SINUMERIK 840D sl) | `adapter/siemens/` |
| Fanuc | `fanuc/` (this repo, unchanged) |
