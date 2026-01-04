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
