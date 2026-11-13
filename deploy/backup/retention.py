"""Which backups to keep. Pure functions, so the policy can be tested.

Policy: every backup from the last `daily` days, plus the first backup of each
of the last `weekly` ISO weeks, plus the first backup of each of the last
`monthly` months. The newest backup is never removed, whatever the dates say.
"""

import datetime as dt
import re

NAME_RE = re.compile(r"^ragconsumer-(\d{8}T\d{6}Z)\.tar\.age$")


def parse_name(name: str) -> dt.datetime | None:
    match = NAME_RE.match(name)
    if not match:
        return None
    return dt.datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)


def select_keep(names: list[str], now: dt.datetime, daily: int = 14, weekly: int = 8, monthly: int = 12) -> set[str]:
    """Returns the names to keep. Names that are not backups are ignored (never kept, never listed for deletion)."""
    dated = sorted(((parse_name(n), n) for n in names if parse_name(n)), key=lambda pair: pair[0])
    if not dated:
        return set()
    keep = {dated[-1][1]}

    today = now.date()
    for when, name in dated:
        if (today - when.date()).days < daily:
            keep.add(name)

    def first_of(bucket_of, limit):
        seen = {}
        for when, name in dated:
            seen.setdefault(bucket_of(when), name)  # dated is ascending: the first one wins
        return [seen[key] for key in sorted(seen)[-limit:]]

    keep.update(first_of(lambda w: w.isocalendar()[:2], weekly))
    keep.update(first_of(lambda w: (w.year, w.month), monthly))
    return keep


def select_delete(names: list[str], now: dt.datetime, **policy) -> list[str]:
    keep = select_keep(names, now, **policy)
    return sorted(n for n in names if parse_name(n) and n not in keep)
