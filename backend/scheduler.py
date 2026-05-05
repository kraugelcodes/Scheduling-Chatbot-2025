"""Scheduling logic for finding candidate time slots in an ICS calendar.

This module exposes a single high-level helper `find_optimal_slot` which
uses a CSP-like approach to find up to three ranked candidate VEVENT blocks
that can be written into the ICS file. The implementation is intentionally
small and heuristic-based (not a full constraint solver) so it's easy to
extend later.

Key helpers:
 - _merge_intervals: merge overlapping busy intervals
 - _find_gaps: compute free gaps inside a search window
 - _score_slot: small heuristic for ranking slots

Agent Use:
 - find_optimal_slot: public API (accepts an event_request dict)
"""

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional
import re
import uuid
from ics_parser import parse_ics_events, events_to_busy_intervals, readable_time_from_event


def __init__(self):
	"""Placeholder initializer for compatibility with import patterns.
	"""
	pass


def _merge_intervals(intervals: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
	"""Merge a list of (start, end) datetime tuples.

	Overlapping or contiguous intervals are merged into a single interval.
	Handles any cases where the working.ics file has overlapping events
	just in case. Could be removed in the future if we can gaurantee no overlaps.

	Args:
		intervals: unsorted list of (start, end) datetimes.

	Returns:
		A sorted list of non-overlapping (start, end) intervals.
	"""
	if not intervals:
		return []
	intervals = sorted(intervals, key=lambda x: x[0])
	merged = [intervals[0]]
	for s, e in intervals[1:]:
		last_s, last_e = merged[-1]
		if s <= last_e:
			merged[-1] = (last_s, max(last_e, e))
		else:
			merged.append((s, e))
	return merged


def _find_gaps(busy: List[Tuple[datetime, datetime]], window_start: datetime, window_end: datetime) -> List[Tuple[datetime, datetime]]:
	"""Compute free time gaps inside [window_start, window_end] given busy intervals.

	The function clips busy intervals to the requested window, merges them,
	and then returns the holes (gaps) where new events could be scheduled.

	Args:
		busy: list of (start, end) busy intervals
		window_start: earliest allowed start datetime
		window_end: latest allowed end datetime

	Returns:
		List of (gap_start, gap_end) tuples representing free time.
	"""
	busy = _merge_intervals([i for i in busy if i[1] > window_start and i[0] < window_end])
	gaps = []
	cursor = window_start
	for s, e in busy:
		if cursor < s:
			gaps.append((cursor, s))
		cursor = max(cursor, e)
	if cursor < window_end:
		gaps.append((cursor, window_end))
	return gaps


def _score_slot(slot_start: datetime, slot_end: datetime, prefer_start: Optional[datetime], prefer_hours: Optional[Tuple[int, int]] = None, target_tz = None) -> float:
	"""Heuristic scoring for candidate slots.

	The score favors:
	  - slots closer to a preferred start (lower distance -> higher score)
	  - slots that begin within `prefer_hours` (big bonus)
	  - slightly longer gaps (small bonus, capped)

	Args:
		slot_start: candidate start datetime (in UTC)
		slot_end: candidate end datetime (in UTC)
		prefer_start: optional datetime to bias towards
		prefer_hours: optional (start_hour, end_hour) tuple to heavily prefer (in local time)
		target_tz: timezone to use for prefer_hours comparison

	Returns:
		Floating point score (higher is better).
	"""
	score = 0.0
	if prefer_start:
		delta = abs((slot_start - prefer_start).total_seconds())
		score -= delta / 3600.0
	
	if prefer_hours and target_tz:
		try:
			slot_local = slot_start.astimezone(target_tz)
			start_h = slot_local.hour
			
			start_pref, end_pref = prefer_hours
			in_range = False
			if start_pref <= end_pref:
				in_range = (start_pref <= start_h < end_pref)
			else:
				in_range = (start_h >= start_pref) or (start_h < end_pref)
			if in_range:
				score += 10.0
		except Exception as e:
			print(f"Warning: Could not convert to target timezone for scoring: {e}")
	
	# longer contiguous free time gets slight bonus (capped at 4 hours)
	duration_hours = (slot_end - slot_start).total_seconds() / 3600.0
	score += min(duration_hours, 4) * 0.5
	minute = slot_start.minute
	if minute == 0 or minute == 30:
		score += 3.0  # small bonus for starting on the hour or half-hour
	elif minute == 15 or minute == 45:
		score += 2.0  # quarter hours
	elif minute % 10 == 0:
		score += 1.0  # ten-minute marks
	return score


def find_optimal_slot(event_request: Dict) -> Dict[str, str]:
	"""Find up to 3 ranked VEVENT strings suitable for the requested event.
	This is the primary method to be called by the AI Agent, and we 
	need to configure the event_request dict from the agent accordingly.
	Need to figure out how we want to parse user intent and format it into request.

	event_request should contain:
	  - duration_minutes: int
	  - window_start: datetime or ISO string (optional, default to start of user requested day)
	  - window_end: datetime or ISO string (optional, default to end of user requested day)
	  - prefer_start: datetime or ISO string (optional)
	  - prefer_hours: (start_hour, end_hour) optional tuple to prefer daily hours in LOCAL time

	Returns a dict {readable_time: vevent_raw, ...}
	"""
	duration = timedelta(minutes=int(event_request.get('duration_minutes', 60)))
	now = datetime.now(timezone.utc)

	def _to_dt(v):
		"""Parse a datetime or ISO string and return a timezone-aware UTC datetime.

		If the input is naive (no tzinfo), assume UTC. Return None for falsy values.
		"""
		if not v:
			return None
		if isinstance(v, datetime):
			dt = v
			if dt.tzinfo is None:
				return dt.replace(tzinfo=timezone.utc)
			return dt.astimezone(timezone.utc)
		if isinstance(v, str):
			try:
				parsed = datetime.fromisoformat(v)
				if parsed.tzinfo is None:
					parsed = parsed.replace(tzinfo=timezone.utc)
				return parsed.astimezone(timezone.utc)
			except Exception:
				try:
					parsed = datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
					return parsed.replace(tzinfo=timezone.utc)
				except Exception:
					raise ValueError(f"Unrecognized datetime format: {v!r}")

	window_start = _to_dt(event_request.get('window_start')) or now
	window_end = _to_dt(event_request.get('window_end')) or (window_start + timedelta(days=7))
	prefer_start = _to_dt(event_request.get('prefer_start'))
	prefer_hours = event_request.get('prefer_hours')
	if prefer_hours:
		prefer_hours = tuple(prefer_hours)
	else:
		prefer_hours = None
	raw_prefer_start = event_request.get('prefer_start')
	raw_window_start = event_request.get('window_start')
	
	def _extract_tz(v):
		"""Extract timezone from a datetime or ISO string."""
		if not v:
			return None
		if isinstance(v, datetime):
			return v.tzinfo
		if isinstance(v, str):
			try:
				parsed = datetime.fromisoformat(v)
				return parsed.tzinfo
			except Exception:
				return None
		return None

	target_tz = _extract_tz(raw_prefer_start) or _extract_tz(raw_window_start) or timezone.utc
	
	print(f"DEBUG: target_tz = {target_tz}")
	print(f"DEBUG: prefer_hours = {prefer_hours}")
	print(f"DEBUG: prefer_start = {prefer_start}")

	events = parse_ics_events('working.ics')
	for event in events:
		print(event)
	busy = events_to_busy_intervals(events)
	normalized_busy = []
	for s, e in busy:
		if s is None or e is None:
			continue
		if s.tzinfo is None:
			s = s.replace(tzinfo=timezone.utc)
		else:
			s = s.astimezone(timezone.utc)
		if e.tzinfo is None:
			e = e.replace(tzinfo=timezone.utc)
		else:
			e = e.astimezone(timezone.utc)
		normalized_busy.append((s, e))
	busy = normalized_busy

	gaps = _find_gaps(busy, window_start, window_end)
	print(f"DEBUG: Found {len(gaps)} gaps:")
	for i, (gap_start, gap_end) in enumerate(gaps):
		gap_start_local = gap_start.astimezone(target_tz)
		gap_end_local = gap_end.astimezone(target_tz)
		print(f"  Gap {i+1}: {gap_start_local.strftime('%a %b %d %H:%M')} - {gap_end_local.strftime('%a %b %d %H:%M')}")

	candidate_slots = []  # list of (score, start, end)
	for gap_start, gap_end in gaps:
		gap_len = gap_end - gap_start
		if gap_len >= duration:
			# Always try earliest, middle, and latest positions
			earliest_start = gap_start
			latest_start = gap_end - duration
			middle_start = earliest_start + (latest_start - earliest_start) / 2
			
			candidates_to_try = [earliest_start, middle_start, latest_start]
			
			if prefer_hours and target_tz:
				gap_start_local = gap_start.astimezone(target_tz)
				gap_end_local = gap_end.astimezone(target_tz)
				current_date = gap_start_local.date()
				end_date = gap_end_local.date()
				
				while current_date <= end_date:
					prefer_dt_local = datetime.combine(current_date, datetime.min.time()).replace(
						hour=prefer_hours[0], minute=0, tzinfo=target_tz
					)
					prefer_dt_utc = prefer_dt_local.astimezone(timezone.utc)
					
					if gap_start <= prefer_dt_utc <= (gap_end - duration):
						candidates_to_try.append(prefer_dt_utc)
					
					mid_hour = (prefer_hours[0] + prefer_hours[1]) // 2
					mid_dt_local = datetime.combine(current_date, datetime.min.time()).replace(
						hour=mid_hour, minute=0, tzinfo=target_tz
					)
					mid_dt_utc = mid_dt_local.astimezone(timezone.utc)
					
					if gap_start <= mid_dt_utc <= (gap_end - duration):
						candidates_to_try.append(mid_dt_utc)
					
					current_date = current_date + timedelta(days=1)

			for candidate_start in candidates_to_try:
				candidate_end = candidate_start + duration
				score = _score_slot(candidate_start, candidate_end, prefer_start, prefer_hours, target_tz)
				candidate_local = candidate_start.astimezone(target_tz)
				print(f"  Evaluating slot: {candidate_local.strftime('%a %b %d %H:%M')} (score={score:.2f})")
				candidate_slots.append((score, candidate_start, candidate_end))

	if not candidate_slots:
		for s, e in busy:
			candidate_start = e
			candidate_end = candidate_start + duration
			if candidate_end <= window_end:
				score = _score_slot(candidate_start, candidate_end, prefer_start, prefer_hours, target_tz)
				candidate_slots.append((score, candidate_start, candidate_end))

	candidate_slots.sort(key=lambda x: x[0], reverse=True)

	# Keep unique starts (avoid near-duplicates) and return top 3
	chosen = []
	seen_starts = set()
	for score, s, e in candidate_slots:
		if s.tzinfo is None:
			s = s.replace(tzinfo=timezone.utc)
		else:
			s = s.astimezone(timezone.utc)
		if e.tzinfo is None:
			e = e.replace(tzinfo=timezone.utc)
		else:
			e = e.astimezone(timezone.utc)
		key = (s.isoformat(), e.isoformat())
		if key in seen_starts:
			continue
		seen_starts.add(key)
		uid = str(uuid.uuid4())
		summary = event_request.get('summary', 'New Event')
		dtstamp = datetime.now(timezone.utc)
		
		dtstart_local = s.astimezone(target_tz)
		dtend_local = e.astimezone(target_tz)
		
		tz_name = str(target_tz)
		if 'UTC' in tz_name and (':' in tz_name or '+' in tz_name or '-' in tz_name):
			if '-05:00' in tz_name or '-04:00' in tz_name:
				tz_name = 'America/New_York'
			else:
				vevent = (
					'BEGIN:VEVENT\n'
					f'UID:{uid}\n'
					f'DTSTAMP:{_format_dt_for_ics(dtstamp)}\n'
					f'DTSTART:{_format_dt_for_ics(s)}\n'
					f'DTEND:{_format_dt_for_ics(e)}\n'
					f'SUMMARY:{summary}\n'
					'END:VEVENT'
				)
				chosen.append((score, vevent, s, e))
				continue
		
		dtstart_str = dtstart_local.strftime('%Y%m%dT%H%M%S')
		dtend_str = dtend_local.strftime('%Y%m%dT%H%M%S')
		
		vevent = (
			'BEGIN:VEVENT\n'
			f'UID:{uid}\n'
			f'DTSTAMP:{_format_dt_for_ics(dtstamp)}\n'
			f'DTSTART;TZID={tz_name}:{dtstart_str}\n'
			f'DTEND;TZID={tz_name}:{dtend_str}\n'
			f'SUMMARY:{summary}\n'
			'END:VEVENT'
		)
		chosen.append((score, vevent, s, e))
		if len(chosen) >= 3:
			break

	result = {}

	def format_local_time(dt, tz):
		"""Format datetime in local timezone for display"""
		try:
			local_dt = dt.astimezone(tz)
			return local_dt.strftime('%a %b %d %Y, %H:%M')
		except Exception as e:
			print(f"Warning: Could not format time in timezone {tz}: {e}")
			return dt.strftime('%a %b %d %Y, %H:%M') + " UTC"

	for score, ve, dtstart, dtend in chosen:
		start_local_str = format_local_time(dtstart, target_tz)
		try:
			end_local = dtend.astimezone(target_tz).strftime('%H:%M')
		except Exception:
			end_local = dtend.strftime('%H:%M') + " UTC"
		
		readable = f"{start_local_str} - {end_local}"
		print(f"DEBUG: Candidate slot - score={score:.2f}, readable={readable}")
		result[readable] = ve
	
	return result


def delete_event(uid: str):
	"""Delete an event by UID from working.ics"""
	events = parse_ics_events("working.ics")
	print(events)
	for i in range(len(events)):
		if events[i]['uid'] == uid:
			events.pop(i)
			break
	print(events)
	file_content = _events_to_ics_string(events)
	print(file_content)
	with open("working.ics", "w") as file:
		file.write(file_content)


def chat(response: str) -> str:
	"""Handle non-scheduling chat responses"""
	return response


def _events_to_ics_string(events: List[Dict]) -> str:
	"""Serialize a list of parsed event dicts back into a minimal VCALENDAR string.

	We keep a simple header/footer and include each event's raw block. This
	mirrors the format used in the sample files in the repo.
	"""
	header = [
		'BEGIN:VCALENDAR',
		'VERSION:2.0',
		'PRODID:-//Default Calendar//EN',
		''
	]
	body_lines = []
	for ev in events:
		raw = ev.get('raw', '')
		raw = raw.strip()
		body_lines.append(raw)

	footer = ['', 'END:VCALENDAR', '']
	return '\n'.join(header + body_lines + footer)


def _replace_prop_in_raw(raw: str, prop: str, value: str) -> str:
	"""Replaces or inserts a property line (e.g. DTSTART, DTEND, SUMMARY) inside a VEVENT block.
	If the property exists (any variation like DTSTART;TZID=...), replace the whole line.
	Otherwise, insert the property just before END:VEVENT.
	"""
	pattern = re.compile(rf'^(?:{prop})(?:[^:\n]*):(.*)$', re.IGNORECASE | re.MULTILINE)
	replacement = f"{prop}:{value}"
	if pattern.search(raw):
		return pattern.sub(replacement, raw)
	return raw.replace('END:VEVENT', replacement + '\n\nEND:VEVENT')


def _format_dt_for_ics(dt_val) -> str:
	"""Normalize a datetime-like value to an ICS datetime string like 20251011T090000Z.
	Accepts a datetime or an ISO string. If None, returns empty string.
	"""
	if dt_val is None:
		return ''
	if isinstance(dt_val, datetime):
		if dt_val.tzinfo is None:
			dt_val = dt_val.replace(tzinfo=timezone.utc)
		else:
			dt_val = dt_val.astimezone(timezone.utc)
		return dt_val.strftime('%Y%m%dT%H%M%SZ')
	try:
		parsed = datetime.fromisoformat(dt_val)
		if parsed.tzinfo is None:
			parsed = parsed.replace(tzinfo=timezone.utc)
		else:
			parsed = parsed.astimezone(timezone.utc)
		return parsed.strftime('%Y%m%dT%H%M%SZ')
	except Exception:
		return str(dt_val)


def edit_event(uid: str, updates: Dict):
	"""Edit a VEVENT in `working.ics`.

	Steps performed:
	  1. Parse current events and find the event by UID.
	  2. Make a shallow copy of the original event dict (returned to caller).
	  3. Update properties provided in `updates`. Date/time values may be datetimes or ISO strings.
	  4. Write the updated events back to `working.ics`.

	Returns a dict with keys 'original_raw' and 'updated_raw' containing the VEVENT
	blocks before and after the edit. original_raw return is for reference only.
	"""
	events = parse_ics_events('working.ics')
	idx = None
	for i, ev in enumerate(events):
		if ev.get('uid') == uid:
			idx = i
			break
	if idx is None:
		raise ValueError(f'Event with UID {uid!r} not found')

	original = events[idx].copy()
	raw = original.get('raw', '')

	existing_tzid = None
	tzid_match = re.search(r'DTSTART;TZID=([^:\n]+):', raw)
	if tzid_match:
		existing_tzid = tzid_match.group(1)

	key_map = {
		'summary': 'SUMMARY',
		'dtstart': 'DTSTART',
		'dtend': 'DTEND',
		'description': 'DESCRIPTION',
		'location': 'LOCATION'
	}

	for k, v in updates.items():
		lk = k.lower()
		if lk not in key_map:
			continue
		prop = key_map[lk]
		if prop in ('DTSTART', 'DTEND'):
			dt_val = None
			if isinstance(v, datetime):
				dt_val = v
			elif isinstance(v, str):
				try:
					dt_val = datetime.fromisoformat(v)
				except Exception:
					pass
			
			if dt_val:
				if existing_tzid:
					try:
						from zoneinfo import ZoneInfo
						target_tz = ZoneInfo(existing_tzid)
					except Exception:
						if dt_val.tzinfo:
							target_tz = dt_val.tzinfo
						else:
							target_tz = timezone.utc
					
					if dt_val.tzinfo is None:
						dt_val = dt_val.replace(tzinfo=timezone.utc)
					dt_local = dt_val.astimezone(target_tz)
					
					dt_str = dt_local.strftime('%Y%m%dT%H%M%S')
					new_val = dt_str
					
					pattern = re.compile(rf'^{prop}(?:;[^:\n]*)?:(.*)', re.IGNORECASE | re.MULTILINE)
					replacement = f"{prop};TZID={existing_tzid}:{new_val}"
					if pattern.search(raw):
						raw = pattern.sub(replacement, raw)
					else:
						raw = raw.replace('END:VEVENT', f'{replacement}\n\nEND:VEVENT')
					continue
				else:
					new_val = _format_dt_for_ics(v)
			else:
				new_val = str(v)
		else:
			new_val = str(v)
		
		if prop not in ('DTSTART', 'DTEND') or not existing_tzid:
			raw = _replace_prop_in_raw(raw, prop, new_val)

	if 'summary' in updates:
		events[idx]['summary'] = updates['summary']
	try:
		if 'dtstart' in updates:
			if isinstance(updates['dtstart'], datetime):
				events[idx]['dtstart'] = updates['dtstart']
			else:
				events[idx]['dtstart'] = datetime.fromisoformat(str(updates['dtstart']))
	except Exception:
		events[idx]['dtstart'] = None
	try:
		if 'dtend' in updates:
			if isinstance(updates['dtend'], datetime):
				events[idx]['dtend'] = updates['dtend']
			else:
				events[idx]['dtend'] = datetime.fromisoformat(str(updates['dtend']))
	except Exception:
		events[idx]['dtend'] = None

	events[idx]['raw'] = raw

	file_content = _events_to_ics_string(events)
	with open('working.ics', 'w', encoding='utf-8') as f:
		f.write(file_content)