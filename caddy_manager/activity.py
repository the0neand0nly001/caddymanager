"""Read pages of the existing audit log without loading the entire file."""

import os
import re

from . import audit

ENTRY = re.compile(r"^\[(.*?)\] IP: (.*?) \| Action: (\S+) \| Details: (.*)$")
PAGE_BYTES = 1024 * 1024


def read_activity(before=None, limit=50):
    try:
        file = open(audit.AUDIT_LOG_FILE, "rb")
    except FileNotFoundError:
        return {"entries": [], "next_cursor": None}
    with file:
        size = file.seek(0, os.SEEK_END)
        end = size if before is None else before
        if end < 0 or end > size:
            raise ValueError(
                "The audit log changed. Refresh to read the newest entries."
            )
        start = max(0, end - PAGE_BYTES)
        file.seek(max(0, start - 1))
        boundary = file.read(1) if start else b"\n"
        file.seek(start)
        data = file.read(end - start)
    if start and boundary != b"\n":
        newline = data.find(b"\n")
        if newline < 0:
            return {"entries": [], "next_cursor": start, "truncated": True}
        start += newline + 1
        data = data[newline + 1 :]
    lines = data.splitlines(keepends=True)
    if lines and not lines[-1].endswith(b"\n"):
        lines.pop()  # A writer may still be appending this entry.
    selected = lines[-limit:]
    cursor = start + sum(map(len, lines[:-limit]))
    entries = []
    for raw in reversed(selected):
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        match = ENTRY.match(line)
        if match:
            timestamp, ip, action, details = match.groups()
        else:
            timestamp, ip, action, details = "", "", "UNPARSED", line
        entries.append(
            {
                "timestamp": timestamp,
                "ip": ip,
                "action": action,
                "details": details[:8192]
                + (" [details truncated]" if len(details) > 8192 else ""),
            }
        )
    return {"entries": entries, "next_cursor": cursor if cursor > 0 else None}
