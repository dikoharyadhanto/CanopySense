export function formatDateTime(
  date: string | Date,
  locale = 'id',
  timeZone = 'Asia/Jakarta',
): string {
  const d = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat(`${locale}-ID`, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone,
  }).format(d);
}

export function formatNumber(value: number, locale = 'id'): string {
  return new Intl.NumberFormat(`${locale}-ID`).format(value);
}
