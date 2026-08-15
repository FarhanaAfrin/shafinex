import { computed } from 'vue'
import { useSession } from '@/stores/session'

/**
 * Every number the user sees goes through here, so the currency, decimal and
 * negative-number preferences apply everywhere at once.
 */
export function useFormat() {
  const session = useSession()
  const prefs = computed(() => session.prefs || {})

  function formatNumber(value, { compact = null, decimals = null } = {}) {
    const number = Number(value ?? 0)
    if (!Number.isFinite(number)) return '—'
    const dp = decimals ?? prefs.value.decimals ?? 0
    const useCompact = compact ?? prefs.value.compact_large_numbers ?? false

    if (useCompact && Math.abs(number) >= 1000) {
      const units = [
        { limit: 1e9, suffix: 'B' },
        { limit: 1e6, suffix: 'M' },
        { limit: 1e3, suffix: 'K' },
      ]
      const unit = units.find((u) => Math.abs(number) >= u.limit)
      const scaled = number / unit.limit
      return `${trimZeros(scaled.toFixed(1))}${unit.suffix}`
    }

    return number.toLocaleString(prefs.value.locale || 'en-US', {
      minimumFractionDigits: dp,
      maximumFractionDigits: dp,
      useGrouping: prefs.value.thousands_separator !== false,
    })
  }

  function formatMoney(value, options = {}) {
    if (value === null || value === undefined || value === '') return ''
    const number = Number(value)
    const negative = number < 0
    const symbol = prefs.value.currency_symbol ?? ''
    const body = formatNumber(Math.abs(number), options)
    const withSymbol =
      prefs.value.symbol_position === 'after' ? `${body}${symbol}` : `${symbol}${body}`

    if (!negative) return withSymbol
    return prefs.value.negative_style === 'parentheses' ? `(${withSymbol})` : `-${withSymbol}`
  }

  /** Empty cells render as a dot so an unfilled month is visibly different from zero. */
  function formatCell(value) {
    if (value === null || value === undefined || value === '') return ''
    return formatMoney(value)
  }

  function formatPercent(value, decimals = 1) {
    if (value === null || value === undefined) return '—'
    return `${Number(value).toFixed(decimals)}%`
  }

  /**
   * Accepts what people actually type: "1,200", "1.2k", "2m", "-450",
   * "1200+300" and "45*12". Returns null for an empty cell.
   */
  function parseAmount(input) {
    if (input === null || input === undefined) return null
    let text = String(input).trim().toLowerCase()
    if (!text) return null

    text = text.replace(/[,\s]/g, '')
    const symbol = (prefs.value.currency_symbol || '').toLowerCase()
    if (symbol) text = text.split(symbol).join('')
    text = text.replace(/[$€£¥₹]/g, '')

    // Parenthesised negatives, accountant style.
    let sign = 1
    if (/^\(.*\)$/.test(text)) {
      sign = -1
      text = text.slice(1, -1)
    }

    text = text.replace(/(\d+(?:\.\d+)?)k/g, (_, n) => String(Number(n) * 1e3))
    text = text.replace(/(\d+(?:\.\d+)?)m/g, (_, n) => String(Number(n) * 1e6))

    if (!/^[-+*/().\d]+$/.test(text)) return NaN

    let result
    if (/[+\-*/]/.test(text.slice(1))) {
      try {
        // Input is already restricted to digits and arithmetic operators above.
        result = Function(`"use strict";return (${text})`)()
      } catch {
        return NaN
      }
    } else {
      result = Number(text)
    }

    if (!Number.isFinite(result)) return NaN
    const dp = prefs.value.decimals ?? 0
    return sign * Number(Number(result).toFixed(dp))
  }

  return { formatMoney, formatNumber, formatCell, formatPercent, parseAmount, prefs }
}

function trimZeros(value) {
  return value.replace(/\.0$/, '')
}
