/**
 * Money-View Utilities for Frontend
 *
 * Purpose: Currency formatting and monetary value display utilities
 * Supports: JPY, USD, EUR with locale-specific formatting
 */

export type Currency = 'JPY' | 'USD' | 'EUR';

export function formatCurrency(
  value: number,
  currency: Currency = 'JPY'
): string {
  if (currency === 'JPY') {
    return `¥${value.toLocaleString('ja-JP', { maximumFractionDigits: 0 })}`;
  } else if (currency === 'USD') {
    return `$${value.toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })}`;
  } else if (currency === 'EUR') {
    return `€${value.toLocaleString('de-DE', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    })}`;
  }
  return `${currency} ${value.toLocaleString()}`;
}

export function formatPercentage(value: number, decimals: number = 1): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(decimals)}%`;
}

export function interpretDelta(delta: number, currency: Currency = 'JPY'): string {
  if (delta > 0) {
    const magnitude = Math.abs(delta) > 10000 ? 'significant' : 'modest';
    return `Positive ${magnitude} profit increase: ${formatCurrency(delta, currency)}`;
  } else if (delta < 0) {
    const magnitude = Math.abs(delta) > 10000 ? 'significant' : 'modest';
    return `Negative ${magnitude} profit decrease: ${formatCurrency(Math.abs(delta), currency)}`;
  } else {
    return 'No significant profit change detected';
  }
}
