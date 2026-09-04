# Optional cppagent helper

Build/install the MTConnect C++ HTTP agent (`/usr/local/bin/agent`).

**Siemens does not use this.** `adapter/siemens/install-systemd.sh` only starts
the Python SHDR server on :7878.

Run by hand if you need HTTP `/current` XML later:

```bash
sudo ./install-cppagent.sh
```
