import { useState } from 'react'
export function useClaudeInsight() {
  const [insight, setInsight] = useState(null)
  const [loading, setLoading] = useState(false)
  const getInsight = async () => {}
  return { insight, loading, getInsight }
}
