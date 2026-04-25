export const formatCurrency = (val) => val != null ? new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val) : '-'
export const formatPerTon = (val) => val != null ? 'Rs ' + Number(val).toLocaleString('en-IN') + '/t' : '-'
export const formatVolume = (val) => val != null ? Number(val).toLocaleString('en-IN') + ' MT' : '-'
export const formatMargin = (val) => val != null ? Number(val).toFixed(1) + '%' : '-'
