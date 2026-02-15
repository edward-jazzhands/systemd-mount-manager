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

Next version:
- entries are normalized into a domain model (device kinds, mount targets,
  option algebra) instead of raw strings.
- resolving `UUID=`, `LABEL=`, `/dev/...` into a unified device model?
- normalizing mount options into structured flags?
- handling continuation lines?
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class FstabEntry:
    device: str
    mount_point: str
    fs_type: str
    options: Sequence[str]
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
    reason: str
    raw_line: str
    line_number: int


FstabLine = FstabEntry | FstabComment | FstabInvalid


def _parse_int(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def parse_fstab_line(line: str, index: int) -> FstabLine | None:
    """Parse a single fstab line into a FstabLine object
    Args:
        line (str): The fstab line to parse
    Returns:
        FstabLine: The parsed fstab line
    """

    stripped: str = line.strip()
    if stripped == "":
        return

    if stripped.startswith("#"):
        return FstabComment(raw_line=line, line_number=index)

    fields: list[str] = stripped.split()

    # fstab entries must have at least 6 fields
    if len(fields) < 6:
        return FstabInvalid(reason="too few fields", raw_line=line, line_number=index)

    # Ignore any fields after the 6th
    device, mount_point, fs_type, options_raw, dump_raw, pass_raw = fields[:6]

    dump_val: int | None = _parse_int(dump_raw)
    pass_val: int | None = _parse_int(pass_raw)

    if dump_val is None or pass_val is None:
        return FstabInvalid(reason="non-integer dump/pass fields", raw_line=line, line_number=index)

    options: list[str] = options_raw.split(",")

    return FstabEntry(
        device=device,
        mount_point=mount_point,
        fs_type=fs_type,
        options=options,
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
        text: str = open("/etc/fstab", "r").read()
    lines: list[str] = text.splitlines()

    parsed_lines = [parse_fstab_line(line, index + 1) for index, line in enumerate(lines)]
    return [line for line in parsed_lines if line is not None]
