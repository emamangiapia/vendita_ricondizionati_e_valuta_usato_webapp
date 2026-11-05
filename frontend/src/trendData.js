const dateFormat = new Intl.DateTimeFormat('it-IT',{day:'2-digit',month:'short',year:'numeric',timeZone:'UTC'});
const dateTimeFormat = new Intl.DateTimeFormat('it-IT',{day:'2-digit',month:'long',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',timeZone:'UTC'});

// Le date memorizzate sono orari locali senza fuso: UTC evita conversioni sul dispositivo di chi guarda.
export function parseExtractionDate(value) {
  if (typeof value !== 'string' || !value) return null;
  const normalized = value.replace(' ', 'T');
  const withZone = /(?:Z|[+-]\d\d:\d\d)$/i.test(normalized) ? normalized : normalized + 'Z';
  const time = Date.parse(withZone);
  return Number.isFinite(time) ? time : null;
}
export const formatAxisDate = time => dateFormat.format(new Date(time));
export const formatExtractionDate = time => dateTimeFormat.format(new Date(time));

export function buildTrend(rows) {
  const grouped = new Map();
  for (const row of rows) {
    const time = parseExtractionDate(row.scanned_at);
    if (time === null || typeof row.price_eur !== 'number' || !Number.isFinite(row.price_eur)) continue;
    const existing = grouped.get(row.scanned_at) || {date:row.scanned_at,time,total:0,count:0,files:new Set()};
    existing.total += row.price_eur;
    existing.count++;
    if (row.filename) existing.files.add(row.filename);
    grouped.set(row.scanned_at, existing);
  }
  return [...grouped.values()].map(item=>({...item,value:item.total/item.count,files:[...item.files]})).sort((a,b)=>a.time-b.time);
}
