// utils/icsParser.js (final fix for fields with parameters)
import moment from 'moment';

const weekdayMap = {
  SU: 0,
  MO: 1,
  TU: 2,
  WE: 3,
  TH: 4,
  FR: 5,
  SA: 6,
};

export function parseICS(icsData) {
  const events = [];
  const seenEvents = new Set();
  const lines = icsData.split(/\r?\n/);
  let currentEvent = null;
  let rrule = null;

  lines.forEach((line) => {
    if (line.startsWith('BEGIN:VEVENT')) {
      currentEvent = {
        title: '',
        start: null,
        end: null,
        location: '',
        description: '',
      };
    } else if (line.startsWith('END:VEVENT')) {
      if (currentEvent && currentEvent.start && currentEvent.end) {
        const eventKey = generateEventKey(currentEvent);
        if (!seenEvents.has(eventKey)) {
          seenEvents.add(eventKey);
          if (rrule) {
            const occurrences = expandRecurrence(currentEvent, rrule, seenEvents);
            occurrences.forEach(event => events.push(event));
          } else {
            events.push(currentEvent);
          }
        }
      }
      currentEvent = null;
      rrule = null;
    } else if (currentEvent) {
      const [rawKey, value] = line.split(/:(.+)/);
      if (!value) return;

      const key = rawKey.split(';')[0]; // Strip off parameters like LANGUAGE=en-us

      if (key === 'SUMMARY') {
        currentEvent.title = value;
      }
      if (key === 'DESCRIPTION') {
        currentEvent.description = value;
      }
      if (key === 'LOCATION') {
        currentEvent.location = value;
      }
      if (key === 'DTSTART') {
        currentEvent.start = parseICSTime(value);
      }
      if (key === 'DTEND') {
        currentEvent.end = parseICSTime(value);
      }
      if (key === 'RRULE') {
        rrule = parseRRule(value);
      }
    }
  });

  return events;
}

function parseICSTime(icsTime) {
  if (icsTime.includes('T')) {
    return moment(icsTime, 'YYYYMMDDTHHmmss').toDate();
  }
  return moment(icsTime, 'YYYYMMDD').toDate();
}

function parseRRule(rruleString) {
  const ruleParts = rruleString.split(';');
  const ruleObj = {};
  ruleParts.forEach(part => {
    const [key, value] = part.split('=');
    ruleObj[key] = value;
  });
  return ruleObj;
}

function expandRecurrence(event, rrule, seenEvents) {
  const occurrences = [];
  const interval = parseInt(rrule.INTERVAL || '1');
  const freq = rrule.FREQ;
  const untilDate = rrule.UNTIL ? moment(rrule.UNTIL, 'YYYYMMDDTHHmmss') : null;
  const byDays = rrule.BYDAY ? rrule.BYDAY.split(',') : [];

  const duration = moment(event.end).diff(moment(event.start));
  let current = moment(event.start);

  if (freq === 'WEEKLY' && byDays.length > 0) {
    let weekStart = moment(event.start).startOf('week');
    while (!untilDate || weekStart.isSameOrBefore(untilDate)) {
      for (let i = 0; i < byDays.length; i++) {
        const day = weekdayMap[byDays[i]];
        if (day === undefined) continue;
        const newStart = moment(weekStart).day(day).hour(current.hour()).minute(current.minute());
        const newEnd = moment(newStart).add(duration);
        if ((!untilDate || newStart.isSameOrBefore(untilDate)) && newStart.isSameOrAfter(event.start)) {
          const occurrence = {
            ...event,
            start: newStart.toDate(),
            end: newEnd.toDate(),
          };
          const key = generateEventKey(occurrence);
          if (!seenEvents.has(key)) {
            seenEvents.add(key);
            occurrences.push(occurrence);
          }
        }
      }
      weekStart.add(interval, 'weeks');
    }
  }

  return occurrences;
}

function generateEventKey(event) {
  return `${event.title.trim().toLowerCase()}-${moment(event.start).format('YYYYMMDDTHHmmss')}-${moment(event.end).format('YYYYMMDDTHHmmss')}`;
}
