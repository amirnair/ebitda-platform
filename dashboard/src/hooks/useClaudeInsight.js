/**
 * useClaudeInsight.js
 * ─────────────────────────────────────────────────────────────────────────────
 * Reusable hook that calls the Anthropic /v1/messages API to generate
 * contextual AI insights for any screen in the platform.
 *
 * Usage:
 *   const { insight, loading, error, refresh } = useClaudeInsight(prompt, deps)
 *
 * The hook is intentionally generic — each screen constructs its own prompt
 * from live data and passes it in. This keeps the API call logic centralised
 * while keeping screen-specific context with the screen.
 *
 * Model: claude-sonnet-4-20250514 (always use Sonnet 4 for in-product calls)
 * ─────────────────────────────────────────────────────────────────────────────
 */
import { useState, useEffect, useCallback, useRef } from "react";

const ANTHROPIC_API = "https://api.anthropic.com/v1/messages";
const MODEL = "claude-sonnet-4-20250514";

/**
 * @param {string|null} prompt  Full prompt string. Pass null to skip fetch.
 * @param {Array}       deps    Re-fetch when any dep changes (like useEffect).
 * @param {object}      [opts]
 * @param {number}      [opts.max_tokens]  Default 350
 * @param {string}      [opts.system]      System prompt override
 */
export function useClaudeInsight(prompt, deps = [], opts = {}) {
  const [insight, setInsight] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState(null);
  const abortRef = useRef(null);

  const fetchInsight = useCallback(async (p) => {
    if (!p) return;

    // Cancel any in-flight request
    if (abortRef.current) abortRef.current.abort();
    abortRef.current = new AbortController();

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(ANTHROPIC_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: abortRef.current.signal,
        body: JSON.stringify({
          model: MODEL,
          max_tokens: opts.max_tokens ?? 350,
          system: opts.system ?? EBITDA_SYSTEM_PROMPT,
          messages: [{ role: "user", content: p }],
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error?.message ?? `API error ${res.status}`);
      }

      const data = await res.json();
      const text = data.content
        .filter(b => b.type === "text")
        .map(b => b.text)
        .join(" ")
        .trim();

      setInsight(text);
    } catch (e) {
      if (e.name === "AbortError") return;
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchInsight(prompt);
    return () => abortRef.current?.abort();
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    insight,
    loading,
    error,
    refresh: () => fetchInsight(prompt),
  };
}

// ── System prompt ──────────────────────────────────────────────────────────
// Kept here so it stays co-located with the API call logic.
// Screens can override via opts.system if they need different behaviour.

const EBITDA_SYSTEM_PROMPT = `You are an EBITDA analyst for a steel TMT rebar manufacturer in Tamil Nadu, India.
You analyse production, sales, and cost data and produce concise, actionable insights for the business owner.

Rules:
- Always respond in 2–3 sentences maximum. No bullet points.
- Lead with the single most important observation (positive or negative).
- End with ONE specific action the owner should consider.
- Use Indian business conventions: Lakhs (L) and Crores (Cr) for currency, MT for metric tonnes.
- Do not mention model names, confidence intervals, or statistical terms.
- Speak as a trusted analyst briefing a founder — direct, specific, no hedging.`;
