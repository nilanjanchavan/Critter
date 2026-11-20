Name:           critter
Version:        0.1.0
Release:        1%{?dist}
Summary:        Customizable Desktop Pet Automation for Linux (Hyprland / Wayland)

License:        MIT
URL:            https://github.com/nilanjanchavan/Critter
Source0:        %{name}-%{version}.tar.gz
Source1:        org.critter.Critter.desktop
Source2:        org.critter.Critter.metainfo.xml
Source3:        critter.service

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-pip
BuildRequires:  python3-wheel
BuildRequires:  desktop-file-utils
BuildRequires:  libappstream-glib

Requires:       python3-gobject
Requires:       gtk4
Requires:       gtk4-layer-shell
Requires:       python3-pillow
Requires:       python3-websockets
Requires:       libnotify

%description
Critter is an extensible Linux desktop pet and automation platform
designed specifically for modern Wayland compositors (Hyprland).
It renders animated, interactive companions directly on the desktop
using GTK4 and Wayland Layer Shell, and features a powerful event-driven
automation engine and local browser companion bridge.

%prep
%autosetup -n %{name}-%{version}

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files critter

# Install desktop entry
install -Dpm 0644 %{SOURCE1} %{buildroot}%{_datadir}/applications/org.critter.Critter.desktop

# Install AppStream metainfo
install -Dpm 0644 %{SOURCE2} %{buildroot}%{_metainfodir}/org.critter.Critter.metainfo.xml

# Install optional systemd user service (disabled by default)
install -Dpm 0644 %{SOURCE3} %{buildroot}%{_userunitdir}/critter.service

# Install default pet packages and automation rules
install -d -m 0755 %{buildroot}%{_datadir}/critter/packages/pets
install -d -m 0755 %{buildroot}%{_datadir}/critter/packages/automations
cp -a packages/pets/* %{buildroot}%{_datadir}/critter/packages/pets/
cp -a packages/automations/* %{buildroot}%{_datadir}/critter/packages/automations/

# Install application icon
install -d -m 0755 %{buildroot}%{_datadir}/icons/hicolor/128x128/apps
install -Dpm 0644 packages/pets/dog/assets/idle_1.png %{buildroot}%{_datadir}/icons/hicolor/128x128/apps/org.critter.Critter.png

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/org.critter.Critter.desktop || true
appstream-util validate-relax --nonet %{buildroot}%{_metainfodir}/org.critter.Critter.metainfo.xml || true

%files -f %{pyproject_files}
%doc README.md
%{_bindir}/critter
%{_datadir}/applications/org.critter.Critter.desktop
%{_metainfodir}/org.critter.Critter.metainfo.xml
%{_userunitdir}/critter.service
%{_datadir}/critter/
%{_datadir}/icons/hicolor/128x128/apps/org.critter.Critter.png

%changelog
* Wed Nov 20 2026 Critter Maintainers <maintainers@critter.local> - 0.1.0-1
- Initial Fedora RPM package release for Critter.

