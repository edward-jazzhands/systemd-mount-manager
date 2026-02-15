"""
logic.fstab.py

In /etc/fstab, every line is one of:

- comment (`# ...`)
- a real entry with 6 fields (device, mountpoint, fstype, options, dump, pass)
- a malformed or partially-specified entry
- empty or whitespace

This version [Done]:
- tokenize lines deterministically
- classify line type
- parse only the canonical 6-field entries into structured data
- preserve everything else as typed variants rather than throwing it away
- entries are normalized into a domain model (device kinds, mount targets,
  option algebra) instead of raw strings.
- resolving `UUID=`, `LABEL=`, `/dev/...` into a unified device model.
- normalizing mount options into structured flags and key-value pairs.

Next version:
- Resolving file system type (fs_type) into structured types
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Sequence
import re


@dataclass(frozen=True)
class DeviceSpec:
    """Represents the parsed device specification.
    ----------
    DEVICE SPECIFICATION MODEL
    ----------
    Linux supports multiple ways to identify block devices in fstab:
    1. UUID=<uuid> - Universally Unique Identifier (most reliable, survives reordering)
    2. LABEL=<label> - Filesystem label (human-readable but must be unique)
    3. PARTUUID=<uuid> - Partition UUID from GPT (distinct from filesystem UUID)
    4. PARTLABEL=<label> - GPT partition label
    5. /dev/sdX - Direct device path (fragile, changes on hardware reconfig)
    6. /dev/disk/by-id/* - Persistent device links by hardware ID
    7. /dev/disk/by-path/* - Persistent links by hardware bus path
    8. /dev/mapper/* - Device mapper targets (LVM, LUKS encryption)
    9. Network paths - //server/share (CIFS), server:/path (NFS)
    10. tmpfs, proc, sysfs - Pseudo-filesystems (no physical device)

    The DeviceSpec model unifies all these into a normalized (kind, value) tuple
    to enable device comparison and resolution logic downstream.
    ----------
    """

    kind: str  # e.g., "UUID", "LABEL", "PARTUUID", "PATH"
    value: str  # The ID or path itself
    raw: str  # The original string

    @classmethod
    def from_string(cls, raw: str) -> DeviceSpec:
        """Parses a device string into a structured spec.

        Args:
            raw (str): The raw device field (e.g. "UUID=123-456" or "/dev/sda1")

        Returns:
            DeviceSpec: The structured device info.

        Examples:
        - "UUID=abc-123" -> DeviceSpec(kind="UUID", value="abc-123", ...)
        - "/dev/sda1" -> DeviceSpec(kind="PATH", value="/dev/sda1", ...)
        - "//server/share" -> DeviceSpec(kind="PATH", value="//server/share", ...)
        """
        if "=" in raw:
            # Handle KEY=VALUE format (UUID, LABEL, etc)
            # Common formats:
            # - UUID=<filesystem-uuid> (from blkid, most common for ext4/xfs/btrfs)
            # - LABEL=<fs-label> (user-defined label, e.g. "BackupDrive")
            # - PARTUUID=<gpt-partition-uuid> (GPT partition table UUID)
            # - PARTLABEL=<gpt-partition-label> (GPT partition name)
            kind, value = raw.split("=", 1)
            return cls(kind=kind.upper(), value=value, raw=raw)

        # Default to PATH if no equals sign is present
        # This handles:
        # - Traditional /dev/sda1, /dev/nvme0n1p1 paths
        # - Pseudo-filesystems: tmpfs, proc, sysfs, devpts, cgroup
        # - Network mounts: //server/share (CIFS), server:/export (NFS)
        # - Device mapper: /dev/mapper/vg-lv (LVM logical volumes)
        # - Encrypted: /dev/mapper/luks-<uuid> (LUKS volumes)
        return cls(kind="PATH", value=raw, raw=raw)


@dataclass(frozen=True)
class MountOptions:
    """Represents parsed mount options (flags vs key-values).

    MOUNT OPTIONS MODEL
    ----------
    Mount options control filesystem behavior and can be:
    1. FLAGS (boolean): rw, ro, noexec, nosuid, nodev, noatime, relatime, etc.
    2. PARAMETERS (key=value): uid=1000, gid=100, mode=0755, iocharset=utf8

    Common option categories:
    - Access control: rw/ro, user/nouser, users, owner
    - Security: nosuid, nodev, noexec (prevent suid binaries, devices, execution)
    - Performance: noatime, relatime, nodiratime (control access time updates)
    - Filesystem-specific:
      * ext4: data=ordered/journal/writeback, barrier=0/1, journal_checksum
      * ntfs/vfat: uid/gid/umask/dmask/fmask (permission mapping for non-Unix FS)
      * nfs: soft/hard, intr, timeo, retrans, rsize, wsize
      * cifs: credentials, username, password, domain, vers=3.0
    - Auto-mount: auto/noauto, _netdev (wait for network before mounting)
    - Errors: errors=remount-ro/continue/panic

    The MountOptions model separates these into structured sets for validation
    and option conflict detection (e.g., rw vs ro, auto vs noauto).
    """

    flags: set[str]
    parameters: dict[str, str]
    raw: str  # The original string

    @classmethod
    def from_raw(cls, options: str) -> MountOptions:
        """Parses a list of option strings into flags and parameters.

        Args:
            options (str): Raw option string (e.g. "rw,noatime,uid=1000")

        Returns:
            MountOptions: The structured options object.

        Example: ["rw", "noatime", "uid=1000"] ->
          MountOptions(flags={"rw", "noatime"}, parameters={"uid": "1000"}, ...)
        """
        # Split comma-separated options into structured flags and parameters
        options_list: list[str] = options.split(",")

        flags: set[str] = set()
        parameters: dict[str, str] = {}

        for opt in options_list:
            if "=" in opt:
                # Key-value parameters (uid=1000, iocharset=utf8, etc.)
                key, val = opt.split("=", 1)
                parameters[key] = val
            else:
                # Boolean flags (rw, ro, noexec, nosuid, etc.)
                flags.add(opt)

        return cls(flags=flags, parameters=parameters, raw=options)


# ===================================================================
# FSTAB LINE MODELS
# ===================================================================
# fstab entries have 6 mandatory fields (space/tab separated):
# 1. device: What to mount (UUID=, /dev/sda1, //server/share, etc.)
# 2. mount_point: Where to mount it (/home, /mnt/data, etc.)
# 3. fs_type: Filesystem type (ext4, xfs, nfs, cifs, tmpfs, etc.)
# 4. options: Mount options (comma-separated, defaults to "defaults")
# 5. dump: Backup operation flag (0=no backup, 1=dump should back this up)
#          Mostly obsolete, usually set to 0
# 6. pass: fsck pass number (0=don't check, 1=check first [root], 2=check after)
#          Root filesystem should be 1, others typically 2, network/virtual=0
#
# Example valid entries:
# UUID=abc-123 / ext4 defaults 0 1
# /dev/sda2 /home xfs noatime,nodev 0 2
# //server/share /mnt/backup cifs credentials=/root/.smbcreds,_netdev 0 0
# tmpfs /tmp tmpfs size=4G,mode=1777 0 0
# server:/export /mnt/nfs nfs soft,intr,rsize=8192,wsize=8192 0 0
# ===================================================================


@dataclass(frozen=True)
class FstabEntry:
    """Represents a valid fstab entry.

    fs_type examples:
    - Local filesystems: ext4, xfs, btrfs, f2fs, jfs, reiserfs
    - FAT filesystems: vfat (FAT32), exfat (for large files)
    - Windows compatibility: ntfs, ntfs-3g (FUSE-based NTFS)
    - Network filesystems: nfs, nfs4, cifs (SMB/Windows shares), afs
    - Pseudo-filesystems: proc, sysfs, tmpfs, devpts, configfs, debugfs
    - Special: swap (swap partition), auto (kernel auto-detect), none
    - Distributed: glusterfs, ceph, lustre
    - Encrypted: fuse (FUSE-based like encfs, sshfs)

    dump field: legacy backup flag for the dump(8) utility
    Almost always set to 0 in modern systems as dump is rarely used
    - 0: don't dump (most common today)
    - 1: dump should back up this filesystem

    pass_num field: determines fsck check order at boot
    fsck runs in parallel on filesystems with the same pass number (if on different drives)
    - 0: don't check (for network mounts, tmpfs, swap)
    - 1: check first (root filesystem only)
    - 2: check after root (all other local filesystems)

    """

    device: DeviceSpec
    mount_point: str
    fs_type: str
    options: MountOptions
    dump: int
    pass_num: int
    raw_line: str
    line_number: int


@dataclass(frozen=True)
class FstabComment:
    raw_line: str
    line_number: int


@dataclass(frozen=True)
class FstabInvalid:
    """Represents an invalid fstab entry.

    Invalid entries occur when:
    - Fewer than 6 fields (incomplete entry, user error)
    - dump/pass fields are non-integer (typo, corruption)
    - Malformed device specification (rare, usually still parseable)

    These are preserved rather than silently dropped to help with error reporting,
    auditing and troubleshooting
    """

    reason: str
    raw_line: str
    line_number: int


# Sum type representing any possible fstab line
# Enables exhaustive pattern matching and type-safe line handling
FstabLine = FstabEntry | FstabComment | FstabInvalid


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _decode_octal(path: str) -> str:
    """Decodes octal escape sequences in fstab paths (e.g., \\040 -> space).

    Args:
        path (str): The raw path string.

    Returns:
        str: The path with octal sequences decoded.

    fstab uses octal escapes like \040 for space.
    This is necessary because fstab is whitespace-delimited, so actual spaces
    in mount points must be escaped. Common escapes:
    - \040 = space (most common, e.g., "/mnt/My\040Files" -> "/mnt/My Files")
    - \011 = tab
    - \012 = newline (rare, technically possible)
    - \134 = backslash (for literal backslash in path)

    Real-world examples:
    - Windows shares: //server/My\040Documents
    - External drives: /media/user/My\040Passport
    - macOS volumes: /Volumes/Macintosh\040HD

    We use regex to find backslash followed by 3 digits.
    """

    def repl(match: re.Match) -> str:
        return chr(int(match.group(1), 8))

    return re.sub(r"\\([0-7]{3})", repl, path)


def parse_fstab_line(line: str, index: int) -> FstabLine | None:
    """Parse a single fstab line into a FstabLine object

    Args:
        line (str): The fstab line to parse
        index (int): The logic line number (accounting for merged lines)

    Returns:
        FstabLine: The parsed fstab line
    """

    stripped: str = line.strip()
    # Empty lines are ignored
    if stripped == "":
        return None

    # Comment lines
    if stripped.startswith("#"):
        return FstabComment(raw_line=line, line_number=index)

    # fstab format is whitespace-delimited, any amount of spaces/tabs separate fields
    fields: list[str] = stripped.split()

    # fstab entries must have at least 6 fields
    # Fewer fields indicate:
    # - Incomplete entry (user still editing)
    # - Corruption (power loss during write)
    # - Copy-paste error
    # - Legacy format misunderstanding
    if len(fields) < 6:
        return FstabInvalid(reason="too few fields", raw_line=line, line_number=index)

    # Ignore any fields after the 6th
    # Ensures we don't capture inline comments or other extra text
    device_raw, mount_raw, fs_type, options_raw, dump_raw, pass_raw = fields[:6]

    # Validate dump and pass are integers
    dump_val: int | None = _parse_int(dump_raw)
    pass_val: int | None = _parse_int(pass_raw)
    if dump_val is None or pass_val is None:
        return FstabInvalid(reason="non-integer dump/pass fields", raw_line=line, line_number=index)

    # Normalize device (Converts raw device string into structured DeviceSpec)
    device_spec = DeviceSpec.from_string(device_raw)

    # Normalize mount point (handle octal escapes)
    # Converts escaped paths to actual paths with spaces/special chars
    # Critical for paths with spaces (common on external drives, Windows shares)
    mount_point = _decode_octal(mount_raw)

    # Normalize options
    mount_options = MountOptions.from_raw(options_raw)

    return FstabEntry(
        device=device_spec,
        mount_point=mount_point,
        fs_type=fs_type,
        options=mount_options,
        dump=dump_val,
        pass_num=pass_val,
        raw_line=line,
        line_number=index,
    )


def parse_fstab(text: str | None = None) -> list[FstabLine]:
    """Parse /etc/fstab into a list of FstabLine objects. If you don't pass in
    text, it will be read from /etc/fstab.

    Note that FstabLine objects are a sum-type of the following:
    - FstabEntry
    - FstabComment
    - FstabInvalid

    Args:
        text (str, optional): The fstab text to parse. Defaults to None.

    Returns:
        list[FstabLine]: The parsed fstab lines
    """

    if text is None:
        # Read from system fstab (/etc/fstab is the canonical location)
        text: str = open("/etc/fstab", "r").read()
    raw_lines: list[str] = text.splitlines()

    # Line numbers are 1-indexed (matches text editor convention)
    parsed_lines = [parse_fstab_line(content, idx + 1) for idx, content in enumerate(raw_lines)]

    # Filter out None (empty lines)
    return [line for line in parsed_lines if line is not None]
