import React from "react"
import { useNavigate, useLocation } from "react-router-dom"
import { useAuth } from "./AuthContext"

export default function AppShell({ children }) {
  const { signOut } = useAuth()
  return (
    <div style={{ display: "flex", height: "100vh" }}>
      <nav style={{ width: 220, background: "#1a1a2e", color: "#fff", padding: "1rem" }}>
        <div style={{ fontWeight: 700, color: "#e2b04a", marginBottom: "1rem" }}>AC Industries</div>
        <button onClick={() => signOut()} style={{ marginTop: "auto", color: "#888" }}>Sign Out</button>
      </nav>
      <main style={{ flex: 1, overflow: "auto", background: "#0f0f1a", color: "#fff" }}>{children}</main>
    </div>
  )
}
