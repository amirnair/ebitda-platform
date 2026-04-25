// src/components/CompanyContext.jsx — Session 9 replacement
//
// The old Session 6 mock CompanyContext is now REPLACED by AuthContext.
// This file becomes a thin re-export shim so that any code that
// previously imported from './CompanyContext' keeps working.
//
// DO NOT delete this file — delete the old contents and replace with this.

export { useCompany, AuthProvider } from './AuthContext'
