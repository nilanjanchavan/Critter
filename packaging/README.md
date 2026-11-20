# Critter Packaging & Systemd Integration

This directory contains packaging artifacts for distributing Critter on Fedora Linux and modern systemd-based Wayland environments.

## Files

- `rpm/critter.spec`: Fedora RPM packaging specification conforming to Fedora 44 Python packaging standards.
- `org.critter.Critter.desktop`: XDG Desktop Application entry for desktop menus and application launchers (`~/.local/share/applications` or `/usr/share/applications`).
- `org.critter.Critter.metainfo.xml`: AppStream metadata (0.14+) specification for software centers (GNOME Software, Discover).
- `critter.service`: Optional systemd user unit to manage Critter as a background session service.

---

## Systemd User Service Instructions

Critter includes an optional systemd user service. **It is disabled by default.**

### Enabling the Service
To enable and start Critter automatically when logging into your Wayland session:

```bash
# 1. Reload the user systemd manager configuration
systemctl --user daemon-reload

# 2. Enable and start the service
systemctl --user enable --now critter.service
```

### Checking Status and Logs
```bash
# Check service status
systemctl --user status critter.service

# View live service journal logs
journalctl --user -u critter.service -f
```

### Stopping and Disabling the Service
```bash
# Stop the running service
systemctl --user stop critter.service

# Disable automatic startup on login
systemctl --user disable critter.service
```
