/**
 * formatCurrency.js
 * ─────────────────────────────────────────────────────────────────────────────
 * INR display utility with Lakhs / Crores threshold logic.
 *
 * Business rule (confirmed with client):
 *   ≥ 1,00,00,000  (1 Cr)   → display in Crores  e.g. "₹4.62 Cr"
 *   ≥ 1,00,000     (1 L)    → display in Lakhs   e.g. "₹38.4 L"
 *   < 1,00,000              → display as amount   e.g. "₹84,200"
 *
 * The owner reads revenue in Crores and EBITDA line items in Lakhs —
 * that is the natural language of the business. Do NOT flatten everything
 * to Lakhs; that destroys context at a glance.
 * ─────────────────────────────────────────────────────────────────────────────
 */

const CRORE  = 10_000_000;   // 1,00,00,000
const LAKH   = 100_000;      // 1,00,000

/**
 * formatCurrency(value, options)
 *
 * @param {number}  value              Raw INR amount
 * @param {object}  [options]
 * @param {string}  [options.symbol]   Currency symbol, default "₹"
 * @param {boolean} [options.compact]  Force shortest form (1 decimal max)
 * @param {number}  [options.decimals] Override decimal places (default: auto)
 * @returns {string}  e.g. "₹4.62 Cr" | "₹38.4 L" | "₹84,200"
 */
export function formatCurrency(value, options = {}) {
  const { symbol = "₹", compact = false, decimals } = options;

  if (value === null || value === undefined || isNaN(value)) return "—";

  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";

  if (abs >= CRORE) {
    const cr = abs / CRORE;
    const dp = decimals ?? (compact ? 1 : cr >= 100 ? 0 : cr >= 10 ? 1 : 2);
    return `${sign}${symbol}${cr.toFixed(dp)} Cr`;
  }

  if (abs >= LAKH) {
    const l = abs / LAKH;
    const dp = decimals ?? (compact ? 1 : l >= 100 ? 0 : l >= 10 ? 1 : 1);
    return `${sign}${symbol}${l.toFixed(dp)} L`;
  }

  // Small amounts — Indian comma formatting
  return `${sign}${symbol}${abs.toLocaleString("en-IN")}`;
}

/**
 * formatPerTon(value)
 * Formats a per-ton realisation / cost value.
 * Always shown as "₹XX,XXX/T" — never in Lakhs/Crores.
 */
export function formatPerTon(value) {
  if (value === null || value === undefined || isNaN(value)) return "—";
  return `₹${Math.round(value).toLocaleString("en-IN")}/T`;
}

/**
 * formatVolume(tons)
 * e.g. 1847 → "1,847 MT"
 */
export function formatVolume(tons) {
  if (tons === null || tons === undefined || isNaN(tons)) return "—";
  return `${Math.round(tons).toLocaleString("en-IN")} MT`;
}

/**
 * formatMargin(ratio)
 * 0.083 → "8.3%"
 */
export function formatMargin(ratio) {
  if (ratio === null || ratio === undefined || isNaN(ratio)) return "—";
  return `${(ratio * 100).toFixed(1)}%`;
}

/**
 * formatDelta(value, options)
 * Returns { text, direction } — direction is "up" | "down" | "flat"
 * Used by KPI cards to pick the correct badge colour.
 *
 * @param {number} value  e.g. 0.112 for +11.2%
 * @param {string} [unit] "pct" (default) | "pp" | "abs"
 */
export function formatDelta(value, unit = "pct") {
  if (value === null || value === undefined || isNaN(value)) {
    return { text: "—", direction: "flat" };
  }
  const direction = value > 0 ? "up" : value < 0 ? "down" : "flat";
  const arrow = value > 0 ? "▲" : value < 0 ? "▼" : "—";
  const abs = Math.abs(value);

  let text;
  if (unit === "pct")  text = `${arrow} ${(abs * 100).toFixed(1)}%`;
  else if (unit === "pp") text = `${arrow} ${(abs * 100).toFixed(1)} pp`;
  else text = `${arrow} ${formatCurrency(abs)}`;

  return { text, direction };
}
