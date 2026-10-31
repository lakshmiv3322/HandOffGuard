import { format } from 'date-fns';

/**
 * Safely format a date or timestamp string/number.
 * Returns a fallback string if the value is null, undefined, invalid, or NaN.
 * Prevents RangeError: Invalid time value from crashing React components.
 */
export function safeFormat(
  dateValue: unknown,
  formatPattern: string,
  fallback = '—',
): string {
  if (
    dateValue === null ||
    dateValue === undefined ||
    dateValue === '' ||
    dateValue === 'None'
  ) {
    return fallback;
  }
  try {
    const d = new Date(dateValue as string | number | Date);
    if (isNaN(d.getTime())) return fallback;
    return format(d, formatPattern);
  } catch {
    return fallback;
  }
}
