export function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

export function formatDateFull(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' });
}

export function formatCurrency(amount: number, currency = 'CNY'): string {
  const symbols: Record<string, string> = {
    CNY: '¥', USD: '$', JPY: '¥', EUR: '€',
    KRW: '₩', THB: '฿', SGD: 'S$', HKD: 'HK$',
    TWD: 'NT$', GBP: '£', AUD: 'A$', AED: 'د.إ',
  };
  const sym = symbols[currency] || currency;
  const formatted = amount.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
  return `${sym}${formatted}`;
}
