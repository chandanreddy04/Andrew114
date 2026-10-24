/** Small helpers for showing times in a friendly way. */

// A clock time like "9:30 PM" (format follows the phone's settings).
export function formatClock(date: Date) {
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

// "Today, 5:29 PM", "Yesterday, 8:02 PM" or "Mon, Oct 13, 7:15 PM".
export function formatWhen(date: Date) {
  const startOfToday = new Date();
  startOfToday.setHours(0, 0, 0, 0);
  const dayMs = 24 * 60 * 60 * 1000;
  const time = formatClock(date);
  if (date.getTime() >= startOfToday.getTime()) return `Today, ${time}`;
  if (date.getTime() >= startOfToday.getTime() - dayMs) return `Yesterday, ${time}`;
  const day = date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
  return `${day}, ${time}`;
}

// A big timer like "00:31:05" (hours:minutes:seconds).
export function formatTimer(ms: number) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const pad = (n: number) => String(n).padStart(2, '0');
  return [
    Math.floor(totalSeconds / 3600),
    Math.floor((totalSeconds % 3600) / 60),
    totalSeconds % 60,
  ]
    .map(pad)
    .join(':');
}

// A length of time like "1h 05m 09s" or "4m 30s".
export function formatDuration(ms: number) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const pad = (n: number) => String(n).padStart(2, '0');

  return hours > 0 ? `${hours}h ${pad(minutes)}m ${pad(seconds)}s` : `${minutes}m ${pad(seconds)}s`;
}

// A number of minutes like "1 hr 15 min" or "45 min".
export function formatMinutes(totalMinutes: number) {
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes} min`;
  if (minutes === 0) return `${hours} hr`;
  return `${hours} hr ${minutes} min`;
}
