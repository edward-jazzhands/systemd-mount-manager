# TO-DO

Main goals:

- [ ] Show you all the app's managed mount status in a dashboard
- [X] Discover existing mounts not app managed
- [ ] "Import" existing mounts into the app to be managed
- [ ] Utilize the newish systemd-mount CLI to create temporary mounts
- [ ] Troubleshoot all managed mounts with the built in troubleshooter
- [ ] Creates folder in home dir at ~/.config/systemd-mount-manager
- [ ] Symlinks files in ~/.config/systemd-mount-manager to /etc/systemd/system
- [ ] User can choose their own directory for managed mount files
- [ ] Detect if managed mount dir is a git repo
- [ ] Offer simple git controls to user in the UI
- [ ] Sudo functions in logic module, enter password in UI popup

TUI mode:

- [ ] Main screen - list of mounts with active/inactive status
- [X] Separate our mounts into 2 categories: This-App, and Discovered
- [ ] Add new mount screen
- [ ] Mount details panel
- [ ] Troubleshooting screen
- [ ] Help screen
- [ ] App preferences screen

GUI mode:

- [ ] blah

Settings:

- [ ] Add validation for input fields
- [ ] managed-mounts-dir actually changes dir
- [ ] Directory picker
- [ ] Extra options modal when changing maaged-mounts-dir

## Notes

- Create credential files as root:root with 600 permissions
- Name them by mount point or share for easy correlation (e.g., nas-media.cred)
- Store a reference/mapping in your managed-mounts metadata so the tool knows which credential file belongs to which mount
- Have the tool detect if a credential file is being used by multiple mounts and warn before deletion, or offer to update credentials across all mounts using that file (Scan your managed mount units for credentials= references when needed)
- Delete references to password in the TUI and GUI apps immediately after getting sudo access in order to ensure the password is not stored in memory

Example:

```md
Credential file 'nas-main.cred' already exists and is used by:
  - /mnt/media (//nas.local/media)
  - /mnt/backups (//nas.local/backups)
  - /mnt/photos (//nas.local/photos)

Overwriting will affect all these mounts.
Continue? [y/N]
```

# ROADMAP


**Phase 1: Core TUI + CLI (roughly 30% complete)

- [x] Prototype CLI demonstrating concept working with pre-made .mount files
- [x] Basic mount detection (systemd units, fstab, temporary)
- [ ] Mount file creation with proper systemd-escape handling
- [x] TUI interface with mount listing and categorization (in progress)
- [x] fstab entry detection and migration flow (in progress)
- [ ] Network share creation (NFS/CIFS) with guided forms
- [x] Sudo prompt + Sudo caching for elevated operations
- [ ] Testing the edge cases (Especially around sudo caching, rollbacks, and preventing users from breaking active mounts)
- [ ] Automount configuration with timeout settings
- [ ] Enable/disable/start/stop mount operations
- [ ] Core logic all usable in pure CLI mode (CLI as separate standalone app).

**Phase 2: Advanced Management**

- [ ] Credential management for authenticated shares
- [ ] Mount testing/validation before commit
- [ ] Git integration detection and status display
- [ ] Systemd journal integration for mount logs
- [ ] Better info views on system mounts and mounts made by other tools
- [ ] Support both credential files and integration with system keyrings (like gnome-keyring or KWallet) simultaneously (Big complexity, but people will love this)

**Phase 3: GUI Implementation

- [ ] GTK interface matching TUI functionality (Copying Textual to GTK 1:1)
- [ ] Unified launcher with `--gui` / `--tui` flags (auto-fallback to TUI if no graphical desktop is available)
- [ ] Desktop integration (.desktop file, app icon) for GTK interface

**Phase 4: Distribution & Future**

- [ ] .deb packages (Debian/Ubuntu)
- [ ] .rpm packages (Fedora/RHEL/openSUSE)
- [ ] AUR package (Arch Linux)
- [ ] Comprehensive documentation and examples
- [ ] Implement Non-interactive mode for scripting key features
- [ ] Support Tailscale credential storage and any other credential backends requested by users 
- [ ] Mounting pattern templates, possible teplate sharing
- [ ] Built-in bug reporting system
- [ ] Custom mount support (bind mounts, tmpfs, etc.) with option to migrate
- [ ] Ability to migrate autofs-generated mounts (excluding wildards / LDAP)
- [ ] Ability to migrate SMB4k-generated mounts
- [ ] Ability to migrate GVFS mounts
