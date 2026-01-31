# systemd-mount-manager

## Type: Desktop/Terminal App

**1 Minute Pitch for busy developers:**
systemd-mount-manager is designed for managing all of the user-changeable mounts that a user can add to systemd that are not part of the OS or kernel. Main focus is on network drive shares using SMB or NFS. Key features are converting fstab entries to permanent .mount files, setting up .automount, integrations with VPNs such as Tailscale / Wireguard (through setting requirements for other services, service load order, etc). Also spport for running `systemd-mount` CLI to make transient mounts, and then offer to convert those mounts into permanent mount files. Key selling point is that its a TUI app that comes with a CLI interface for all essential features so its usable anywhere on any system or over SSH. It is more versatile than existing solutions like SMB4k (due to being a TUI and thus not dependent on KDE, also can do NFS), and much easier to use than autofs or attempting to script `systemd-mount` to run every login

---
## The Problem

If you use Linux with systemd, you've probably dealt with mounting network shares, managing fstab entries, or wrestling with systemd unit files. The current tooling landscape is fragmented and frustrating:

**Managing mounts is still stuck in the past:**

- Hand-editing `/etc/fstab` with cryptic syntax where one typo can prevent boot
- Writing `.mount` unit files where the filename must match the mount path exactly (using `systemd-escape`)
- No unified view of what mounts exist across fstab, systemd units, and temporary mounts
- Migrating legacy fstab entries to modern systemd mounts is tedious and error-prone
- Managing network share credentials securely requires manual file editing
- No easy way to replicate mount configurations across multiple machines

**The existing tools fall short:**

- `systemd-mount` only creates temporary mounts that disappear on reboot
- GVFS mounts are also temporary and disappear on reboot, in addition
- GNOME Disks and KDE Partition Manager focus mainly on local block devices
- fstab is a legacy format that lacks the robustness of systemd mounts (failures can block boot, poor error handling, no automatic retries)
- autofs / automount is powerful, but far too complex for most home users
- There's no standard tool that shows ALL your mounts (fstab, systemd units, temporary mounts) in one place
- Most solutions require deep systemd knowledge and comfort with manual config editing

---
## The Solution

**systemd-mount-manager** is the unified interface for managing all systemd mounts on Linux. It brings together fstab entries, permanent systemd mounts, and temporary mounts into a single, intuitive interface: available as both a TUI (terminal UI) and GUI.

This project evolved from a personal bash script for bootstrapping network mounts. After realizing the broader need for unified systemd mount management tooling, the scope expanded to become a full-featured application addressing the gap in the Linux ecosystem.

Systemd's mount capabilities are powerful: better error handling, non-blocking failures, automatic retries, and superior logging compared to fstab. But the tooling to actually _use_ these features has been missing. systemd-mount-manager finally provides a modern interface to modern mount management.

This project aims to hit two targets with one pitch. Experienced sysadmins will appreciate how it can convert fstab entries and simplify the process of managing .mount files while still allowing you to use git to back up them up. Meanwhile, regular linux users that just want an easy way to set up SMB and NFS shares to their homelab will appreciate finally having a GUI app that makes this feel like a native experience. And everyone will appreciate the built in auto-troubleshooter wizard that can detect exactly why your network mount is not working.

systemd-mount-manager's TUI is built with [Textual](https://textual.textualize.io/), the modern Python framework for building sophisticated terminal user interfaces. As an active Textual community member (contributor to Textual core, author of [CLOCTUI](https://www.github.com/edward-jazzhands/cloctui), and creator of multiple Textual plugins), this project showcases what's possible with modern TUI development: smooth animations, responsive layouts, and an interface that feels as polished as any GUI. The fully de-coupled architecture allows the Textual Interface, the GTK interface, and the CLI (made with Click) to all share the same core logic. The CLI also aims to expose enough functionality that it's scriptable, so it can eventually be built into bash scripts, Ansible, Cloud init, web admin panels, docker containers, or whatever else people think of.

**Core Features:**

**One-Click Migrations**

- Automatically detect and convert legacy fstab entries to robust systemd mount units
- Preserve all mount options and configurations
- Optionally comment out migrated fstab entries
- Get modern mount management without losing existing setups
- [Future Goal] Also migrate mounts made by a variety of other tools (autofs, SMB4k, GVFS, etc. Note we can't do autofs wildcards or LDAP, that's never happening.)

**Unified Mount Management**

- View ALL mounts in one place: managed, fstab-generated, temporary, autofs-generated, and system mounts
- See what's actually mounted, what's configured, and what's managed by what tool.
- Detect if mounts were generated by other tools such as autofs or SMB4k
- Clear visual distinction between managed (editable), system (read-only), and temporary mounts
- Filter and search across all mount types

**Network Share Specialization**

- First-class support for NFS and CIFS/SMB mounts with tailored UIs
- Network share discovery over mDNS, the same mechanism used by GVFS discovery in most Linux file managers
- Secure credential management for authenticated shares, done on the proper channel: credential files owned by root with permissions set to 600. These are stored in /etc by default but you can change the directory.
- Network-aware options (timeouts, `_netdev`, automount on access)
- Test connections before committing configurations

**Full Systemd Integration**

- Generates correct `.mount` and `.automount` unit files with proper naming
- Handles `systemd-escape` path conversion automatically
- Enable, disable, start, stop, and reload mounts with one click
- View systemd logs for mount failures right in the interface
- Utilize systemd-mount CLI for creating and viewing transient mounts

**Infrastructure as Code Ready**

- Store managed mounts in a git-versioned directory (default: `~/.config/systemd-mount-manager`). Managed mount files are symlinked into /etc/systemd/system.
- Sync configurations across machines with simple `git clone`
- Version control your mount infrastructure like dotfiles
- Script-friendly: all configs are plain systemd unit files
- Git remains optional: The program will suggest it as it has built in git features, but version controlling the mount files is not required for any functionality. Only for power users.

**Triple Interface, true decoupled architecture**

- **TUI (Textual)** - Primary interface, perfect for SSH sessions and headless servers
- **GUI (GTK)** - Desktop-friendly version with identical functionality
- **CLI (Click)** - Scriptable and pure-text interface. Runs as its own independent app with an entry binary. The TUI and the GUI do all commands through the CLI, and it's usable by itself
- Single installation, choose your interface with a flag
- No X11 forwarding or VNC needed for remote management
- Independent CLI logic means someone else could even write their own GUI for it in whatever language they want. Integrate it into admin web apps, Ansible scripts, or even write your own GUI in Qt if you really want to.

**Tracking managed mounts**

- 100% file based unix-philosophy. The program scans the specified managed mounts folder, /etc/systemd/system, and compares.
- Users can freely git clone or git fetch and the app will refresh.
- Dropping in files manually is totally acceptable
- Files remain the source of truth for mount configurations. They'll keep working fine if the program gets uninstalled or stops working.

**Built in troubleshooter

Troubleshooter is one of the key features and possibly the app's true killer pitch. It is designed to programatically detect exactly why a network share is not connected and give the user a report + guide on how to fix it. This can be set to trigger automatically when a mount fails or run on demand. It detects and reports problems such as:

- Was the mount unit never started, or did it start and fail?
- Did it fail because a dependency wasn’t active or is missing?
- Did it time out waiting for the network?
- Did name resolution fail vs authentication fail vs permission denied?
- Is the remote reachable but exporting the wrong path?
- Is automount configured but not being triggered?

**Who it's for:**

- **System administrators** managing mounts across multiple servers
- **Infrastructure engineers** who want version-controlled, reproducible configurations
- **Home lab enthusiasts** running NAS devices and network storage
- **DevOps teams** standardizing mount management across environments
- **Anyone** tired of the fstab/systemd mount management mess

## Some Technical Notes

Technical stack is Python with Textual framework for TUI, PygObject + GTK for the GUI, Click framework for the CLI.

Mount files managed by the app are stored in a folder of the user's choosing, default `~/.config/systemd-mount-manager/managed-mounts`. Managed mount files are symlinked into /etc/systemd/system on demand. Sudo access is only needed for these few key elevated operations, allowing for free editing of the mount files without sudo. It will utilize sudo caching for the TUI side, and Polkit for the GUI side. By using password prompts for only key operations and then relying on OS-level sudo caching, we can avoid needing the user to run the entire program as root.
Everything of course will be built around safe operations so we need backups of any things we may modify, rollbacks, dry run mode, pre-validation of mount files, etc. Furthermore, once mount files have been sylinked then modifying the managed file can break the mount so we will need systems to prevent that. Working on temporary files is a good solution here.

The CLI exposes the core operations needed to manage mounts and is meant to be stable and scriptable. It is not intended to expose every internal helper or parsing function. Internally, the project has a logic module that’s just a collection of pure functions (no state, no classes). The TUI and GUI import these directly because they’re written in Python.

If you want to interact with systemd-mount-manager programatically in some way (scripts, web admin panels, integration into other GUIs, etc), and you’re writing your app/tool in Python, you can save yourself time by importing systemd-mount-manager.logic as a library. If you’re writing in another language, the CLI will get you most of the way there, but anything beyond that will mean re-implementing parts of the logic layer. That’s expected. The logic module is deliberately written using pure, stateless functions, so it should be easy to translate into another language if you want deeper integration.

A note on migrations from autofs / SMB4k / etc - This is a lofty goal, it's certainly something I'd like to see in the future but I'm well aware that it's going to be very complex and its not a high priority. Good for long-term motivation though!

A note about mDNS: This is mostly for home users, AFAIK it's not normally used in any kinds of corporate environments or cloud VLANs, so trying to support mDNS for pro or corporate environments does not make any sense, thus there's no need for any kind of advanced subdomain searching or anything like that. I think whatever your desktop file manager does is fine for us.

A note about marketing / this pitch: This is a technical pitch, designed for contributors as well as technical users interested in what's happening under the hood. For the actual website front page and github readme I would write something that's directed for regular users with a banner that says "For technical users / Sysadmins, click here to jump straight to the advanced pitch".

---
## Why Existing Solutions Fall Short

When you mention needing better mount management tools, you'll inevitably hear: "Just use SMB4K" or "autofs already does this" or "my file manager handles network shares fine." Let's address these head-on.

### File Manager Network Browsing (Dolphin, Nautilus, Thunar, etc.)

**What they do:** Modern file managers can browse and "mount" network shares through GVFS/KIO backends.

**Why it's not enough:**
- **Session-only mounts** - Disappear on logout/reboot. Not suitable for anything you need reliably available.
- **User-space FUSE mounts** - Other users can't access them. System services can't access them. They live in hidden `.gvfs` directories, not where you actually want your mounts.
- **Zero control** - You get whatever mount options GVFS decides. Need specific CIFS versions? Custom timeouts? Network dependency ordering? Out of luck.
- **Not infrastructure** - Can't version control, can't replicate across machines, can't script.

File managers are great for *browsing* shares. But if you need your media library, backup destination, or development files to be reliably available system-wide across reboots, GVFS mounts aren't the answer.

### SMB4K

**What it does:** Mature KDE application for mounting CIFS/SMB shares with a GUI, credential management, and automatic remounting.

**Why it's not enough:**
- **CIFS-only** - No NFS support. Homelab users running Linux file servers are left out.
- **KDE ecosystem lock-in** - Requires KDE frameworks. If you're on anything GNOME-based, you're pulling in heavy dependencies. On headless servers,  it's not an option at all.
- **Custom daemon architecture** - SMB4K runs its own service to manage mounts. If the daemon crashes or fails to start, your mounts are gone. It's another moving part to maintain.
- **No remote management** - Can't SSH into a headless server and manage mounts. Requires a graphical environment.
- **No infrastructure-as-code story** - Configurations are stored in SMB4K's own database format. Can't version control, can't easily sync across machines.
- **Limited systemd integration** - Doesn't leverage systemd's dependency ordering, so handling VPN dependencies or ensuring mounts wait for network services is manual work.

SMB4K is a solid tool for what it does, but it's designed for a specific use case: KDE desktop users mounting Windows shares. It doesn't address the broader mount management problem or the infrastructure-as-code workflow.

### autofs / automount

**What it does:** Enterprise-grade automounting system with powerful features like LDAP-backed maps, wildcard patterns, and on-demand mounting.

**Why it's not enough:**
- **Complexity overkill** - Designed for enterprise scenarios (thousands of users, centralized directory services, dynamic share allocation). For mounting 3-10 shares to your home NAS, it's like using a forklift to move a chair.
- **Separate daemon and configuration syntax** - Another service to manage, another config format to learn (not standard systemd units).
- **Poor discoverability** - Most Linux users don't even know it exists, and the documentation assumes enterprise knowledge.
- **No GUI or friendly tooling** - You're editing config files in `/etc/auto.master` and debugging mount maps. There's no "create mount" wizard.

autofs is the right tool if you're managing an enterprise with LDAP-integrated home directories. For homelab users who just want to mount their NAS properly, it's overkill. systemd's built-in automounting is simpler, better integrated, and sufficient for 99% of home and small business use cases - but nobody knows how to use it properly because there's no tooling.

### Manual systemd Unit Files

**What it does:** The "proper" way - writing `.mount` and `.automount` unit files by hand.

**Why it's not enough:**
- **Steep learning curve** - You need to understand systemd unit syntax, `systemd-escape` path encoding, dependency ordering, and mount option syntax.
- **Error-prone** - One typo in the filename (which must match the mount path exactly after systemd-escape conversion) and it won't work. Misconfigured dependencies can cause boot hangs.
- **No discoverability** - Most users don't even know systemd can do persistent mounts (despite the fact that systemd actually converts fstab entries into persistent mount files on every boot). The documentation exists but isn't beginner-friendly.
- **Tedious repetition** - Creating 10 mounts means writing either 10 or 20 unit files by hand, ensuring consistent options, and managing credentials separately.
- **No unified view** - No way to see all your mounts (fstab, systemd, temporary) in one place. No tooling to help troubleshoot failures.

This is the "correct" solution, but it's inaccessible to most users. systemd-mount-manager makes the correct solution actually usable.

### Legacy fstab

**What it does:** The traditional `/etc/fstab` file for defining mounts at boot.

**Why it's not enough:**
- **Boot-blocking failures** - A misconfigured fstab entry can prevent your system from booting. You'll be dropped to an emergency shell.
- **Poor error handling** - No automatic retries on failure, no graceful degradation beyond basic `nofail`. Mount fails? Your boot process either hangs or continues without the mount.
- **Cryptic syntax** - One typo can break your system. No validation before reboot. The `x-systemd.*` options exist but are poorly documented and easy to get wrong.
- **Hidden complexity** - Modern fstab *can* use systemd features (`x-systemd.requires=`, `x-systemd.after=`, `x-systemd.automount`), but now you're mixing two configuration paradigms. You're writing systemd directives inside fstab syntax, getting the worst of both worlds: fstab's fragility with systemd's complexity.
- **No proper tooling** - No way to validate your fstab before rebooting. No unified view of what's actually configured. Troubleshooting failures means parsing `journalctl` output manually.
- **Legacy format holds you back** - Even with `x-systemd.*` extensions, you're still constrained by fstab's line-based format. Separate credential files, complex dependency chains, and detailed systemd integration are awkward to express clearly.

The `x-systemd.*` options are a bandaid - they let you bolt systemd features onto fstab, but you're still editing a single system-critical file with no validation, no structure, and no safety net. If you're going to use systemd features, why not use actual systemd unit files that give you proper syntax, validation, and modularity? Systemd-Mount-Manager finally makes it easy with automated fstab migrations.

### What systemd-mount-manager Actually Solves

We're not replacing these tools - we're filling the gap they all leave open:

- **Benefits over file manager (GVFS) mounts:**  Persistent, system-wide mounts with full control over options and dependencies.
- **Benefits over SMB4K:** Works on any desktop environment, supports NFS, uses native systemd (not a custom daemon), manageable over SSH via TUI.
- **Benefits over autofs:** Leverages systemd's simpler automounting for the 99% of users who don't need enterprise features, without a separate daemon or obscure config syntax.
- **Benefits over hand rolling systemd units:**  Friendly UI (TUI/GUI) that generates correct unit files for you. Handles `systemd-escape`, dependency ordering, and validation automatically.
- **Benefits over editing fstab:** Modern systemd mounts with proper error handling, easier syntax, and more stability - plus a migration tool to convert your legacy fstab entries painlessly.

**The real value:** systemd-mount-manager is the first tool that makes systemd's powerful mount capabilities actually accessible to normal users, while still being infrastructure-as-code friendly for power users and sysadmins.

If you're already happy with SMB4K, autofs, or GVFS - great! Keep using them. But if you've ever thought "there has to be a better way to do this," that's what I'm building.

---

## Real-World Case Studies

**Real-World Use Case: Network Share Discovery (mDNS + Tailscale)**

Finding network shares is often harder than configuring them. systemd-mount-manager includes built-in discovery to surface mountable shares automatically.

The app can:

- Discover hosts advertising SMB or NFS shares via **mDNS** (the same mechanism used by modern Linux file managers)
- Query **Tailscale** (with sudo authorization) to retrieve Magic DNS hostnames on your tailnet
- Probe discovered hosts for available SMB/CIFS and NFS exports

Detected shares are presented as mount candidates. Selecting one launches the standard mount creation wizard, ensuring all mounts go through the same validated, systemd-native flow with proper dependencies, automounting, and credential handling.

This mirrors how GVFS discovers network locations, but instead of creating temporary, session-scoped mounts, systemd-mount-manager helps users turn discovered shares into **persistent systemd mounts** that survive reboots and work system-wide.

**Real-World Use Case: Network Mounts Over VPN**

One of the most frustrating scenarios with fstab: you have a NAS accessible over Tailscale (or any VPN), and your fstab mount tries to connect at boot before the VPN is up. Result? Boot hangs, mount failures, or you resort to hacky sleep delays in init scripts.

systemd mounts solve this elegantly:

- **Dependency ordering:** `Requires=tailscaled.service` + `After=tailscaled.service` ensures the mount waits for your VPN to be running
- **Automounting:** Mount on first access means by the time you actually need the share, Tailscale is definitely up
- **Non-blocking failures:** If the VPN isn't available, your system still boots normally instead of hanging

systemd-mount-manager makes this trivial to set up. When creating a network mount, just check "Requires service" and enter the name of your service (ie tailscaled). The tool handles the unit file dependencies automatically. No more boot hangs, no more manual systemd syntax, no more wondering why your NAS share isn't available after reboot.
Note: Tailscale has first-class support throughout the app. I'll certainly want to support other common services in this first class manner. I'll be open to taking requests to get other popular services people might want. (ie Wireguard, other VPNs, network services, etc. I'm sure there's more out there).

---
## Is This You?

**Scenario 1: The fstab Survivor**

Your `/etc/fstab` looks like this:

```
//nas/media /mnt/media cifs credentials=/root/.smbcreds,uid=1000 0 0
server:/export /mnt/nfs nfs defaults 0 0
```

It works... until your VPN isn't up at boot and your system hangs for 90 seconds. Or until you fat-finger an edit and can't boot. You've added `noauto` or `_netdev` or `x-systemd.automount` after Googling cryptic errors. You're patching a 1980s solution with modern bandaids.

fstab entries block boot on failure, can't express complex dependencies cleanly, and one typo away from an emergency shell.

**What you actually need:** Modern systemd mounts that fail gracefully, support proper dependency ordering (`Requires=tailscaled.service`), and give you actual error messages in the journal. systemd-mount-manager migrates your fstab entries automatically.

**Scenario 2: The Startup Script Warrior**

```bash
# Your ~/.bashrc or startup script
systemd-mount -t cifs //nas.local/media /mnt/media
systemd-mount -t nfs server:/backups /mnt/backups
sleep 5  # pray the network is up
systemd-mount -t cifs //192.168.1.50/downloads /mnt/downloads
````

You discovered `systemd-mount` exists. You're running it in startup scripts, `.bashrc`, or cron jobs. It _mostly_ works... except when it doesn't. Sometimes the network isn't ready yet. Sometimes you get weird race conditions. You've added `sleep` delays that feel like voodoo. You're _so close_ to doing it right.

`systemd-mount` creates temporary mounts. They're gone after unmount or reboot. You're fighting against the tool instead of using proper persistent mounts with dependency ordering.

**What you actually need:** Permanent `.mount` units that wait for the network, handle failures gracefully, and automount on access.

**Scenario 3: The Manual Unit File Masochist**

You've read the systemd documentation. You _know_ `.mount` files are the right way. You've learned `systemd-escape`. You've written units by hand:

```ini
[Unit]
Description=NAS Media
After=network-online.target
Requires=tailscaled.service

[Mount]
What=//nas.local/media
Where=/mnt/media
Type=cifs
Options=credentials=/etc/smbcreds

[Install]
WantedBy=multi-user.target
```

This is exactly what I was doing. Until I realized I wanted a way to recreate this easily on a different device or OS install. So then I set up a github repo with a bootstrapper script to automate that process for me. Then I realized I wanted to add some options to my bootstrapper script. Then I realized there was edge cases that needed handling, and I wanted a nicer interface than a boring CLI prompt...

You can imagine that this quickly becomes tedious without any kind of automation. Every new mount is 15 minutes of editing, escaping paths, and double-checking syntax. If you're a programmer as I am (or just a fan of efficiency in general) then you'll quickly succumb to the urge to try to automate this in some way. And once you're doing that, the rabbit hole goes very, very deep.

**What you actually need:** Tooling that generates these correctly for you without getting in the way of your work flow. You still get proper systemd units, you still get git versioning, you still understand what's happening. But you're not hand rolling your own files and bootstrapper scripts. If you tried to go down the path of automating this process, as I did, you'll likely end up recreating much of the same functionality. 

