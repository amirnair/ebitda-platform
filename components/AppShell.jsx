// src/components/AppShell_session9_diff.jsx
// ─────────────────────────────────────────────────────────────
// SESSION 9 CHANGES TO AppShell.jsx
// Apply these additions to the existing AppShell from Session 6.
// Do NOT rewrite the whole file — only patch these sections.
// ─────────────────────────────────────────────────────────────
//
// CHANGE 1 — Add this import at the top of AppShell.jsx:
//
//   import { useAuth } from './AuthContext'
//   import { ROLE_LABELS, ROLE_COLOURS } from '../config/rolePermissions'
//
// CHANGE 2 — Add UserChip component (paste below your existing helper components):
//
// function UserChip() {
//   const { profile, signOut } = useAuth()
//   if (!profile) return null
//   const c = ROLE_COLOURS[profile.role] ?? ROLE_COLOURS.viewer
//   return (
//     <div style={{ display:'flex', alignItems:'center', gap:'0.5rem' }}>
//       {/* Name */}
//       <span style={{ fontSize:'0.75rem', color:'#8899AA', fontFamily:"'DM Mono', monospace" }}>
//         {profile.full_name ?? 'User'}
//       </span>
//       {/* Role badge */}
//       <span style={{
//         background: c.bg, color: c.text,
//         padding: '2px 8px', borderRadius: 4,
//         fontSize: '0.7rem', fontFamily:"'DM Mono', monospace",
//         letterSpacing: '0.06em',
//       }}>
//         {ROLE_LABELS[profile.role] ?? profile.role}
//       </span>
//       {/* Sign out */}
//       <button
//         onClick={signOut}
//         style={{
//           background: 'none', border: '1px solid #1E3A5F',
//           borderRadius: 4, color: '#8899AA', cursor: 'pointer',
//           padding: '2px 8px', fontSize: '0.7rem',
//           fontFamily:"'DM Mono', monospace", letterSpacing: '0.06em',
//         }}
//       >
//         Sign out
//       </button>
//     </div>
//   )
// }
//
// CHANGE 3 — In the page header JSX, add <UserChip /> to the top-right:
//
//   <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', ... }}>
//     <h2 style={styles.pageTitle}>{currentScreen?.label}</h2>
//     <UserChip />                    {/* ← ADD THIS */}
//   </div>
//
// CHANGE 4 — In the nav items loop, hide screens the user can't access.
//   Add this import at the top:
//     import { canAccess } from '../config/rolePermissions'
//   Then in the nav loop:
//     {Object.entries(screens)
//       .filter(([key]) => canAccess(role, key))   // ← ADD THIS LINE
//       .map(([key, screen]) => (
//         <NavItem ... />
//       ))
//     }
//   And get role from useAuth():
//     const { role } = useAuth()
//
// ─────────────────────────────────────────────────────────────
// That's it. Four targeted changes. Everything else in AppShell
// is unchanged from Session 6.
// ─────────────────────────────────────────────────────────────

export {} // keep this file as a valid ES module
