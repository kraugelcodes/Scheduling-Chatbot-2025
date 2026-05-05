from datetime import datetime
import re
from typing import List, Dict


def _parse_ics_datetime(value: str) -> datetime:
    # Handles formats like 20251011T090000Z or 20251011T090000 or 20251011
    value = value.strip()
    if value.endswith('Z'):
        value = value[:-1]
    try:
        if 'T' in value:
            if len(value) in (15, 14):
                return datetime.strptime(value, '%Y%m%dT%H%M%S')
            else:
                return datetime.strptime(value, '%Y%m%dT%H%M')
        else:
            return datetime.strptime(value, '%Y%m%d')
    except Exception:
        digits = re.sub(r"[^0-9]", "", value)
        if len(digits) >= 8:
            return datetime.strptime(digits[:8], '%Y%m%d')
        raise


def parse_ics_events(file_path: str) -> List[Dict]:
    """Parse an .ics file and return a list of VEVENT dicts.

    Each dict contains keys: uid, summary, dtstart (datetime), dtend (datetime), raw (str)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    events = []
    for match in re.finditer(r'BEGIN:VEVENT(.*?)END:VEVENT', content, re.DOTALL | re.IGNORECASE):
        block = match.group(1)
        props = {}
        for line in block.splitlines():
            line = line.strip()
            if not line or ':' not in line:
                continue
            key, val = line.split(':', 1)
            props[key.upper()] = val.strip()

        dtstart_raw = props.get('DTSTART') or props.get('DTSTART;VALUE=DATE') or props.get('DTSTART;TZID=')
        dtend_raw = props.get('DTEND') or props.get('DTEND;VALUE=DATE')
        uid = props.get('UID', '')
        summary = props.get('SUMMARY', '').strip()

        try:
            dtstart = _parse_ics_datetime(dtstart_raw) if dtstart_raw else None
            dtend = _parse_ics_datetime(dtend_raw) if dtend_raw else None
        except Exception:
            dtstart = None
            dtend = None

        events.append({'uid': uid, 'summary': summary, 'dtstart': dtstart, 'dtend': dtend, 'raw': 'BEGIN:VEVENT' + block + 'END:VEVENT'})

    return events


def events_to_busy_intervals(events: List[Dict]):
    """Convert parsed events into a list of (start, end) datetimes for busy intervals.

    Events with missing start/end are ignored.
    """
    intervals = []
    for ev in events:
        s = ev.get('dtstart')
        e = ev.get('dtend')
        if s and e:
            # ensure start < end
            if s > e:
                s, e = e, s
            intervals.append((s, e))
    # sort
    intervals.sort(key=lambda x: x[0])
    return intervals


def readable_time_from_event(event_or_raw) -> str:
    """Return a human-readable string for an event's DTSTART/DTEND.

    Accepts either a parsed event dict (as returned by `parse_ics_events`) or
    a raw VEVENT string. Returns strings like "Sat Oct 11 2025, 09:00 - 10:00"
    or "Oct 11 2025 (all day)" if only a date was provided. Mostly for testing
    but could use for NLP output later.
    """
    ev = None
    if isinstance(event_or_raw, dict):
        ev = event_or_raw
    elif isinstance(event_or_raw, str):
        # try to parse a single VEVENT block quickly
        m = re.search(r'BEGIN:VEVENT(.*?)END:VEVENT', event_or_raw, re.DOTALL | re.IGNORECASE)
        block = m.group(1) if m else event_or_raw
        props = {}
        for line in block.splitlines():
            line = line.strip()
            if not line or ':' not in line:
                continue
            key, val = line.split(':', 1)
            props[key.upper()] = val.strip()

        try:
            dtstart = _parse_ics_datetime(props.get('DTSTART') or props.get('DTSTART;VALUE=DATE') or props.get('DTSTART;TZID='))
        except Exception:
            dtstart = None
        try:
            dtend = _parse_ics_datetime(props.get('DTEND') or props.get('DTEND;VALUE=DATE'))
        except Exception:
            dtend = None
        ev = {'dtstart': dtstart, 'dtend': dtend}
    else:
        raise ValueError('Unsupported event_or_raw type')

    s = ev.get('dtstart')
    e = ev.get('dtend')
    if not s and not e:
        return 'Unknown time'
    
    # If only start present
    if s and not e:
        if s.hour == 0 and s.minute == 0 and s.second == 0:
            return s.strftime('%a %b %d %Y (all day)')
        return s.strftime('%a %b %d %Y, %H:%M')

    # If both present
    # Normalize if date-only (00:00:00) -> treat as all-day
    if s.hour == 0 and s.minute == 0 and s.second == 0 and e.hour == 0 and e.minute == 0 and e.second == 0:
        # show date range
        if s.date() == e.date():
            return s.strftime('%a %b %d %Y (all day)')
        return f"{s.strftime('%b %d %Y')} - {e.strftime('%b %d %Y')} (all day)"

    # If same day, show times
    if s.date() == e.date():
        return f"{s.strftime('%a %b %d %Y')}, {s.strftime('%H:%M')} - {e.strftime('%H:%M')}"

    # Multi-day event with times
    return f"{s.strftime('%b %d %Y %H:%M')} - {e.strftime('%b %d %Y %H:%M')}"
