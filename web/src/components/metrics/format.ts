const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];
const WEEKDAYS_FULL = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// Parse "YYYY-MM-DD" in the local timezone (new Date("YYYY-MM-DD") parses as
// UTC midnight, which shifts the weekday for negative UTC offsets).
function parseDay(dateStr: string): Date | null {
  const [y, m, d] = dateStr.split('-').map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

export function formatCompact(n: number): string {
  if (Math.abs(n) >= 10_000) return `${Math.round(n / 1000)}k`;
  if (Math.abs(n) >= 1_000) return `${(n / 1000).toFixed(1)}k`;
  return n.toLocaleString();
}

export function isWeekend(dateStr: string): boolean {
  const d = parseDay(dateStr);
  if (!d) return false;
  const day = d.getDay();
  return day === 0 || day === 6;
}

/** "Sa 9" — axis tick for daily charts. */
export function formatDayTick(dateStr: string): string {
  const d = parseDay(dateStr);
  if (!d) return dateStr;
  return `${WEEKDAYS[d.getDay()]} ${d.getDate()}`;
}

/** "Sat, Aug 9" — tooltip label for daily charts. */
export function formatDayFull(dateStr: string): string {
  const d = parseDay(dateStr);
  if (!d) return dateStr;
  return `${WEEKDAYS_FULL[d.getDay()]}, ${MONTHS[d.getMonth()]} ${d.getDate()}`;
}

/** "14" — axis tick for hourly charts (local hour of day). */
export function formatHourTick(hourIso: string): string {
  const d = new Date(hourIso);
  if (isNaN(d.getTime())) return hourIso;
  return String(d.getHours());
}

/** "14:00 – 15:00" — tooltip label for hourly charts (local time). */
export function formatHourFull(hourIso: string): string {
  const d = new Date(hourIso);
  if (isNaN(d.getTime())) return hourIso;
  const h = d.getHours();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(h)}:00 – ${pad((h + 1) % 24)}:00`;
}

// Region-name lookup via Intl.DisplayNames, falling back to the raw ISO code
// when the API is unavailable (old Safari) or the code is invalid.
let regionNames: Intl.DisplayNames | null | undefined;

export function countryName(code: string): string {
  if (regionNames === undefined) {
    try {
      regionNames = new Intl.DisplayNames(['en'], { type: 'region' });
    } catch {
      regionNames = null;
    }
  }
  if (!regionNames) return code;
  try {
    return regionNames.of(code.toUpperCase()) || code;
  } catch {
    return code;
  }
}

export function getCountryFlag(countryCode: string): string {
  if (!countryCode || countryCode.length !== 2) return '🏳️';
  const codePoints = countryCode
    .toUpperCase()
    .split('')
    .map((char) => 127397 + char.charCodeAt(0));
  return String.fromCodePoint(...codePoints);
}
