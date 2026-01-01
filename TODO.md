# TODO

Main goals::
[-] Show you all the app's managed mount status in a dashboard
[✔️] Discover existing mounts not app managed
[-] "Import" existing mounts into the app to be managed
[-] Utilize the newish systemd-mount CLI to create temporary mounts
[-] Troubleshoot all managed mounts with the built in troubleshooter
[-] Creates folder in home dir at ~/.config/systemd-mount-manager
[-] Symlinks files in ~/.config/systemd-mount-manager to /etc/systemd/system
[-] User can choose their own directory for managed mount files
[-] Detect if managed mount dir is a git repo
[-] Offer simple git controls to user in the UI
[-] Sudo functions in logic module, enter password in UI popup

TUI mode:
[-] Main screen - list of mounts with active/inactive status
[✔️] Separate our mounts into 2 categories: This-App, and Discovered
[-] Add new mount screen
[-] Mount details panel
[-] Troubleshooting screen
[-] Help screen
[-] App preferences screen

GUI mode:
[-] blah

Settings:
[-] Managed Mounts Directory (default ~/.config/systemd-mount-manager/managed-mounts)
