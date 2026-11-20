# Critter 🐾

**Customizable Desktop Pet & Automation Platform for Linux (Hyprland / Wayland)**

[![Fedora](https://img.shields.io/badge/Fedora-44-blue.svg)](https://fedoraproject.org/)
[![Hyprland](https://img.shields.io/badge/Compositor-Hyprland%20(Wayland)-00bcd4.svg)](https://hyprland.org/)
[![GTK4](https://img.shields.io/badge/GUI-GTK4%20%2B%20Layer%20Shell-4a90e2.svg)](https://github.com/wmww/gtk4-layer-shell)
[![Python](https://img.shields.io/badge/Python-3.14%2B-yellow.svg)](https://python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Critter brings adorable, customizable cartoon animals to live on your Linux desktop. More than just a visual novelty, Critter is an event-driven automation platform where pets have independent movement, distinct personalities, and configurable responsibilities.

---

## 🌟 Features

- **Native Wayland Layer Shell**: Built directly for **Fedora + Hyprland** using GTK4 Layer Shell.
- **Non-Intrusive**:
  - Full alpha transparency (no background boxes or borders).
  - Configured with `KeyboardMode.NONE` and `exclusive_zone = 0` so it never steals keyboard focus or shifts your tiled windows.
  - Sized per pet (`128×128`) so all clicks outside the animal naturally pass through to your background applications.
- **Silky-Smooth Dragging**: High-performance Hyprland UNIX IPC cursor tracking (~0.02ms query latency) ensures jitter-free drag & drop.
- **Genuine Kawaii Cartoon Artwork**: Pure vector-rendered frame animations (idle breathing, happy eye-smile blink, walking cycles, dangling drag pose).
- **Decoupled Architecture**: Pure Python business logic and typed synchronous event bus completely isolated from GTK/Wayland UI code.
- **Data-Driven Pet Packages**: Pets are defined by declarative `manifest.json` packages, making community creation and sharing easy.

---

## 🏗️ Project Architecture

```text
critter/
├── apps/
│   └── desktop/
│       ├── bootstrap.py         # Dynamic linker preload for gtk4-layer-shell
│       ├── cursor.py            # Low-latency Hyprland IPC cursor tracking
│       ├── pet_window.py        # Transparent GTK4 Layer Shell window & dragging
│       └── main.py              # Application lifecycle & CLI entrypoint
│
├── core/
│   ├── events.py                # Synchronous, strongly typed pub/sub event bus
│   └── pet.py                   # Pure Python pet models & autonomous roaming physics
│
├── packages/
│   └── pets/
│       └── dog/
│           ├── manifest.json    # Pet metadata, animation frame rates, speeds
│           ├── generate_assets.py # Vector Cairo asset generator
│           └── assets/          # 128x128 RGBA transparent sprite frames
│
└── tests/
    ├── test_events.py           # Event bus unit tests
    └── test_pet.py              # Controller & manifest unit tests
```

---

## 🚀 Getting Started

### Prerequisites (Fedora Linux)
Ensure you have Python 3, GTK4, and GTK4 Layer Shell installed:
```bash
sudo dnf install gtk4 gtk4-layer-shell python3-gobject python3-cairo
```

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/nilanjanchavan/Critter.git
   cd Critter
   ```

2. Create a virtual environment using system site-packages (to inherit native GTK bindings):
   ```bash
   python3 -m venv --system-site-packages .venv
   .venv/bin/pip install pytest
   ```

3. Launch your desktop pet:
   ```bash
   .venv/bin/python3 -m critter.apps.desktop.main
   ```

### Controls
- **Left-Click & Drag**: Pick up and drag the pet smoothly anywhere on your monitors.
- **Release**: The pet resumes idle animations and autonomous roaming.
- **Terminal Exit**: Press `Ctrl+C` in the launching terminal for a graceful exit.

---

## 🧪 Running Tests

Critter maintains a rigorous unit test suite covering core physics, coordinate clamping, and the event bus:

```bash
.venv/bin/pytest tests/
```

---

## 🗺️ Roadmap

- [x] **Phase 1**: Wayland Layer Shell foundation, isolated bootstrap, synchronous event bus.
- [x] **Phase 2**: Kawaii Corgi rendering, idle/walking/dragging animations, Hyprland IPC smooth dragging.
- [ ] **Phase 3**: Multi-pet manager & pet package registry (introducing the Cat).
- [ ] **Phase 4**: Event-driven automation engine (timers, notifications, action registries).
- [ ] **Phase 5**: WebExtension browser integration (tab tracking, website activity monitors).
- [ ] **Phase 6**: Community pet importing & package distribution.
- [ ] **Phase 7**: Settings UI & Fedora RPM/Flatpak packaging.
