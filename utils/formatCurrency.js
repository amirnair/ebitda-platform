export const formatCurrency = (val) => val != null ? new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val) : '-'
export const formatPerTon = (val) => val != null ? \Rs \/t\ : '-'
export const formatVolume = (val) => val != null ? \\ MT\ : '-'
export const formatMargin = (val) => val != null ? \\%\ : '-'
