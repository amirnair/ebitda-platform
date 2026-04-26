// src/screens/Settings.jsx
// Screen 10 — Settings
// Tabs: Company Info | Users | SKU Master | Benchmarks
// Users tab: full user management for admin/owner roles.

import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabaseClient'
import { useAuth } from '../components/AuthContext'
import { useCompany } from '../components/AuthContext'
import { ROLE_LABELS, ROLE_COLOURS, ROLES } from '../config/rolePermissions'

const TABS = ['Company', 'Users', 'SKU Master', 'Benchmarks']

export default function Settings() {
  const { role }    = useAuth()
  const company     = useCompany()
  const [tab, setTab] = useState('Company')
  const isAdmin = role === ROLES.OWNER || role === ROLES.ADMIN

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Settings</h1>
          <p style={styles.subtitle}>{company.company_name} — Platform Configuration</p>
        </div>
      </div>

      {/* Tab bar */}
      <div style={styles.tabBar}>
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={tab === t ? { ...styles.tab, ...styles.tabActive } : styles.tab}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={styles.content}>
        {tab === 'Company'    && <CompanyTab company={company} isAdmin={isAdmin} />}
        {tab === 'Users'      && <UsersTab isAdmin={isAdmin} />}
        {tab === 'SKU Master' && <SkuMasterTab />}
        {tab === 'Benchmarks' && <BenchmarksTab />}
      </div>
    </div>
  )
}

// ── Company Tab ───────────────────────────────────────────────────────────────
function CompanyTab({ company }) {
  const rows = [
    ['Company Name',        company.company_name],
    ['Platform Slug',       company.company?.slug ?? '—'],
    ['Industry',            company.company?.industry ?? 'steel'],
    ['Subscription Tier',   company.subscription_tier],
    ['Primary Colour',      company?.primary_colour],
    ['Secondary Colour',    company?.secondary_colour],
  ]

  return (
    <div style={styles.section}>
      <SectionHeader title="Company Information" />
      <table style={styles.infoTable}>
        <tbody>
          {rows.map(([label, value]) => (
            <tr key={label}>
              <td style={styles.infoLabel}>{label}</td>
              <td style={styles.infoValue}>
                {label.includes('Colour')
                  ? <ColourSwatch hex={value} />
                  : <span style={label === 'Subscription Tier' ? styles.tierBadge : {}}>{value}</span>
                }
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={styles.helpNote}>
        To change company settings, contact your platform administrator or raise a support request.
      </p>
    </div>
  )
}

function ColourSwatch({ hex }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
      <div style={{ width: 16, height: 16, borderRadius: 3, background: hex, border: '1px solid #333' }} />
      <span>{hex}</span>
    </div>
  )
}

// ── Users Tab ─────────────────────────────────────────────────────────────────
function UsersTab({ isAdmin }) {
  const { company } = useCompany()
  const [users,      setUsers]    = useState([])
  const [loading,    setLoading]  = useState(true)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole,  setInviteRole]  = useState('viewer')
  const [inviteName,  setInviteName]  = useState('')
  const [inviting,   setInviting]   = useState(false)
  const [inviteMsg,  setInviteMsg]  = useState(null)
  const [editingId,  setEditingId]  = useState(null)
  const [editRole,   setEditRole]   = useState('')

  async function loadUsers() {
    setLoading(true)
    const { data, error } = await supabase
      .from('profiles')
      .select('id, full_name, role, is_active, created_at')
      .order('created_at', { ascending: true })

    if (!error) setUsers(data ?? [])
    setLoading(false)
  }

  useEffect(() => { loadUsers() }, [])

  async function handleInvite() {
    if (!inviteEmail || !inviteRole) return
    setInviting(true)
    setInviteMsg(null)

    // Supabase invite user — sends magic link email
    const { error } = await supabase.auth.admin.inviteUserByEmail(inviteEmail, {
      data: {
        company_id: company?.id,
        full_name:  inviteName,
        role:       inviteRole,
      }
    })

    if (error) {
      setInviteMsg({ type: 'error', text: error.message })
    } else {
      setInviteMsg({ type: 'success', text: `Invite sent to ${inviteEmail}` })
      setInviteEmail('')
      setInviteName('')
      setInviteRole('viewer')
      loadUsers()
    }
    setInviting(false)
  }

  async function handleRoleChange(userId, newRole) {
    const { error } = await supabase
      .from('profiles')
      .update({ role: newRole, updated_at: new Date().toISOString() })
      .eq('id', userId)

    if (!error) {
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, role: newRole } : u))
    }
    setEditingId(null)
  }

  async function toggleActive(userId, currentStatus) {
    const { error } = await supabase
      .from('profiles')
      .update({ is_active: !currentStatus })
      .eq('id', userId)

    if (!error) {
      setUsers(prev => prev.map(u => u.id === userId ? { ...u, is_active: !currentStatus } : u))
    }
  }

  if (!isAdmin) {
    return (
      <div style={styles.restricted}>
        🔒 User management requires Admin or Owner role.
      </div>
    )
  }

  return (
    <div style={styles.section}>
      {/* Invite new user */}
      <SectionHeader title="Invite User" />
      <div style={styles.inviteRow}>
        <input
          style={styles.inviteInput}
          placeholder="Full name"
          value={inviteName}
          onChange={e => setInviteName(e.target.value)}
        />
        <input
          style={{ ...styles.inviteInput, flex: 2 }}
          placeholder="Email address"
          type="email"
          value={inviteEmail}
          onChange={e => setInviteEmail(e.target.value)}
        />
        <select
          style={styles.inviteSelect}
          value={inviteRole}
          onChange={e => setInviteRole(e.target.value)}
        >
          {Object.entries(ROLE_LABELS).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
        <button
          style={inviting ? { ...styles.inviteBtn, opacity: 0.5 } : styles.inviteBtn}
          onClick={handleInvite}
          disabled={inviting}
        >
          {inviting ? 'SENDING...' : 'INVITE'}
        </button>
      </div>
      {inviteMsg && (
        <div style={inviteMsg.type === 'error' ? styles.errorMsg : styles.successMsg}>
          {inviteMsg.text}
        </div>
      )}

      {/* Users table */}
      <SectionHeader title="Current Users" style={{ marginTop: '2rem' }} />
      {loading ? (
        <div style={styles.loading}>Loading users...</div>
      ) : (
        <table style={styles.usersTable}>
          <thead>
            <tr>
              {['Name','Email','Role','Status','Joined','Actions'].map(h => (
                <th key={h} style={styles.th}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} style={u.is_active ? {} : styles.inactiveRow}>
                <td style={styles.td}>{u.full_name ?? '—'}</td>
                <td style={styles.td}><span style={styles.mono}>{u.id.slice(0,8)}…</span></td>
                <td style={styles.td}>
                  {editingId === u.id ? (
                    <select
                      style={styles.inlineSelect}
                      value={editRole}
                      onChange={e => setEditRole(e.target.value)}
                    >
                      {Object.entries(ROLE_LABELS).map(([val, label]) => (
                        <option key={val} value={val}>{label}</option>
                      ))}
                    </select>
                  ) : (
                    <RoleBadge role={u.role} />
                  )}
                </td>
                <td style={styles.td}>
                  <span style={u.is_active ? styles.activeBadge : styles.inactiveBadge}>
                    {u.is_active ? 'Active' : 'Inactive'}
                  </span>
                </td>
                <td style={styles.td}>
                  <span style={styles.mono}>
                    {new Date(u.created_at).toLocaleDateString('en-IN', { day:'2-digit', month:'short', year:'numeric' })}
                  </span>
                </td>
                <td style={styles.td}>
                  {editingId === u.id ? (
                    <div style={{ display:'flex', gap:4 }}>
                      <ActionBtn label="Save" onClick={() => handleRoleChange(u.id, editRole)} colour="#E8B84B" textColour="#0D1B2A" />
                      <ActionBtn label="Cancel" onClick={() => setEditingId(null)} />
                    </div>
                  ) : (
                    <div style={{ display:'flex', gap:4 }}>
                      <ActionBtn label="Edit Role" onClick={() => { setEditingId(u.id); setEditRole(u.role) }} />
                      <ActionBtn
                        label={u.is_active ? 'Deactivate' : 'Activate'}
                        onClick={() => toggleActive(u.id, u.is_active)}
                        colour={u.is_active ? '#FF6B6B' : '#4CAF50'}
                      />
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

// ── SKU Master Tab ────────────────────────────────────────────────────────────
function SkuMasterTab() {
  const SKUs = [
    { brand:'P1', size:'8mm',  code:'P1-SKU-8',  billet:'Product 1 Billet', length:'6M' },
    { brand:'P1', size:'10mm', code:'P1-SKU-10', billet:'Product 1 Billet', length:'6M' },
    { brand:'P1', size:'12mm', code:'P1-SKU-12', billet:'Product 1 Billet', length:'6M' },
    { brand:'P1', size:'16mm', code:'P1-SKU-16', billet:'Product 1 Billet', length:'6M' },
    { brand:'P1', size:'20mm', code:'P1-SKU-20', billet:'Product 1 Billet', length:'6M' },
    { brand:'P1', size:'25mm', code:'P1-SKU-25', billet:'Product 1 Billet', length:'5.6M' },
    { brand:'P1', size:'32mm', code:'P1-SKU-32', billet:'Product 1 Billet', length:'5.05M' },
    { brand:'P2', size:'8mm',  code:'P2-SKU-8',  billet:'Product 2 Billet', length:'6M' },
    { brand:'P2', size:'10mm', code:'P2-SKU-10', billet:'Product 2 Billet', length:'6M' },
    { brand:'P2', size:'12mm', code:'P2-SKU-12', billet:'Product 2 Billet', length:'6M' },
    { brand:'P2', size:'16mm', code:'P2-SKU-16', billet:'Product 2 Billet', length:'6M' },
    { brand:'P2', size:'20mm', code:'P2-SKU-20', billet:'Product 2 Billet', length:'6M' },
    { brand:'P2', size:'25mm', code:'P2-SKU-25', billet:'Product 2 Billet', length:'5.6M' },
    { brand:'P2', size:'32mm', code:'P2-SKU-32', billet:'Product 2 Billet', length:'4.9M' },
  ]

  return (
    <div style={styles.section}>
      <SectionHeader title="SKU Master" />
      <p style={styles.helpNote}>Read-only. SKU master is defined in companyConfig.js and validated by sku_master.py.</p>
      <table style={styles.usersTable}>
        <thead>
          <tr>{['Brand','Size','Product Code','Billet Type','Billet Length'].map(h => (
            <th key={h} style={styles.th}>{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {SKUs.map(sku => (
            <tr key={sku.code}>
              <td style={styles.td}><BrandBadge brand={sku.brand} /></td>
              <td style={{ ...styles.td, ...styles.mono }}>{sku.size}</td>
              <td style={{ ...styles.td, ...styles.mono }}>{sku.code}</td>
              <td style={styles.td}>{sku.billet}</td>
              <td style={{ ...styles.td, ...styles.mono }}>{sku.length}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Benchmarks Tab ────────────────────────────────────────────────────────────
function BenchmarksTab() {
  const benchmarks = [
    { param: 'Mill Capacity',      value: '18–25 MT/hr', note: 'Size-graduated. 8mm=18, 32mm=25' },
    { param: 'Rolling Factor',     value: '1.05',         note: 'Uniform — 1.05 tons billet → 1 ton TMT' },
    { param: 'Changeover Time',    value: '2 hours',      note: 'Per SKU switch on mill' },
    { param: 'Mill Runtime',       value: '16 hrs/day',   note: 'Standard per Decision Report' },
    { param: 'P1 Target Share',    value: '70%',          note: 'Strategic target — not in forecast engine' },
    { param: 'P2 Target Share',    value: '30%',          note: 'Managed decline target' },
    { param: 'Monthly Volume Target', value: '2,200 MT', note: 'Strategic milestone' },
    { param: 'EBITDA Margin Target',  value: '18%',       note: 'Strategic milestone' },
  ]

  return (
    <div style={styles.section}>
      <SectionHeader title="Benchmarks & Targets" />
      <p style={styles.helpNote}>
        Benchmark overrides coming in a future session. Values are currently sourced from companyConfig.js.
      </p>
      <table style={styles.usersTable}>
        <thead>
          <tr>{['Parameter','Value','Notes'].map(h => (
            <th key={h} style={styles.th}>{h}</th>
          ))}</tr>
        </thead>
        <tbody>
          {benchmarks.map(b => (
            <tr key={b.param}>
              <td style={styles.td}>{b.param}</td>
              <td style={{ ...styles.td, ...styles.mono, color: '#E8B84B' }}>{b.value}</td>
              <td style={{ ...styles.td, color: '#8899AA', fontSize: '0.78rem' }}>{b.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Shared sub-components ─────────────────────────────────────────────────────
function SectionHeader({ title }) {
  return (
    <div style={styles.sectionHeader}>
      <span>{title}</span>
      <div style={styles.sectionLine} />
    </div>
  )
}

function RoleBadge({ role }) {
  const c = ROLE_COLOURS[role] ?? ROLE_COLOURS.viewer
  return (
    <span style={{
      background:   c.bg,
      color:        c.text,
      padding:      '2px 8px',
      borderRadius: 4,
      fontSize:     '0.72rem',
      fontFamily:   "'DM Mono', monospace",
      letterSpacing: '0.06em',
    }}>
      {ROLE_LABELS[role] ?? role}
    </span>
  )
}

function BrandBadge({ brand }) {
  const isP1 = brand === 'P1'
  return (
    <span style={{
      background:   isP1 ? '#1E3A5F' : '#2A1A40',
      color:        isP1 ? '#E8B84B' : '#DDA0DD',
      padding:      '2px 8px',
      borderRadius: 4,
      fontSize:     '0.72rem',
      fontFamily:   "'DM Mono', monospace",
    }}>{brand}</span>
  )
}

function ActionBtn({ label, onClick, colour = '#1E3A5F', textColour = '#FFFFFF' }) {
  return (
    <button
      onClick={onClick}
      style={{
        background:   colour,
        color:        textColour,
        border:       'none',
        borderRadius: 4,
        padding:      '3px 8px',
        fontSize:     '0.7rem',
        fontFamily:   "'DM Mono', monospace",
        cursor:       'pointer',
        letterSpacing: '0.05em',
      }}
    >
      {label}
    </button>
  )
}

// ── Styles ────────────────────────────────────────────────────────────────────
const C = {
  bg:      '#0D1B2A',
  surface: '#111F30',
  border:  '#1E3A5F',
  gold:    '#E8B84B',
  text:    '#FFFFFF',
  muted:   '#8899AA',
}

const styles = {
  page: {
    padding:   '1.5rem 2rem',
    fontFamily: "'DM Mono', monospace",
    color:     C.text,
    minHeight: '100%',
  },
  header: {
    display:        'flex',
    justifyContent: 'space-between',
    alignItems:     'flex-start',
    marginBottom:   '1.5rem',
  },
  title: {
    margin: 0,
    fontSize: '1.5rem',
    fontWeight: 700,
    fontFamily: "'Syne', sans-serif",
    color: C.text,
  },
  subtitle: {
    margin: '0.25rem 0 0',
    fontSize: '0.78rem',
    color: C.muted,
  },
  tabBar: {
    display:       'flex',
    gap:           '0.25rem',
    borderBottom:  `1px solid ${C.border}`,
    marginBottom:  '1.5rem',
  },
  tab: {
    background:    'none',
    border:        'none',
    borderBottom:  '2px solid transparent',
    color:         C.muted,
    padding:       '0.6rem 1rem',
    cursor:        'pointer',
    fontSize:      '0.78rem',
    fontFamily:    "'DM Mono', monospace",
    letterSpacing: '0.06em',
    transition:    'color 0.15s',
  },
  tabActive: {
    color:         C.gold,
    borderBottom:  `2px solid ${C.gold}`,
  },
  content: {},
  section: {
    maxWidth: 900,
  },
  sectionHeader: {
    display:        'flex',
    alignItems:     'center',
    gap:            '0.75rem',
    marginBottom:   '1rem',
    fontSize:       '0.72rem',
    color:          C.muted,
    letterSpacing:  '0.1em',
    textTransform:  'uppercase',
  },
  sectionLine: {
    flex:       1,
    height:     1,
    background: C.border,
  },
  infoTable: {
    width:          '100%',
    borderCollapse: 'collapse',
    marginBottom:   '1rem',
  },
  infoLabel: {
    padding:   '0.5rem 0.75rem',
    color:     C.muted,
    fontSize:  '0.78rem',
    width:     200,
    verticalAlign: 'middle',
  },
  infoValue: {
    padding:   '0.5rem 0.75rem',
    color:     C.text,
    fontSize:  '0.85rem',
    fontFamily: "'DM Mono', monospace",
    verticalAlign: 'middle',
  },
  tierBadge: {
    background: '#1E3A5F',
    color:      C.gold,
    padding:    '2px 8px',
    borderRadius: 4,
    fontSize:   '0.75rem',
    textTransform: 'capitalize',
  },
  helpNote: {
    fontSize:   '0.75rem',
    color:      C.muted,
    marginTop:  '0.5rem',
    lineHeight: 1.6,
    fontStyle:  'italic',
  },
  inviteRow: {
    display:   'flex',
    gap:       '0.5rem',
    marginBottom: '0.75rem',
    flexWrap:  'wrap',
  },
  inviteInput: {
    flex:         1,
    background:   '#0A1520',
    border:       `1px solid ${C.border}`,
    borderRadius: 6,
    padding:      '0.55rem 0.75rem',
    color:        C.text,
    fontSize:     '0.82rem',
    fontFamily:   "'DM Mono', monospace",
    outline:      'none',
    minWidth:     120,
  },
  inviteSelect: {
    background:   '#0A1520',
    border:       `1px solid ${C.border}`,
    borderRadius: 6,
    padding:      '0.55rem 0.75rem',
    color:        C.text,
    fontSize:     '0.82rem',
    fontFamily:   "'DM Mono', monospace",
    outline:      'none',
  },
  inviteBtn: {
    background:   C.gold,
    color:        '#0D1B2A',
    border:       'none',
    borderRadius: 6,
    padding:      '0.55rem 1.25rem',
    fontSize:     '0.78rem',
    fontFamily:   "'DM Mono', monospace",
    fontWeight:   700,
    letterSpacing: '0.08em',
    cursor:       'pointer',
  },
  errorMsg: {
    color:     '#FF6B6B',
    fontSize:  '0.78rem',
    marginBottom: '0.5rem',
  },
  successMsg: {
    color:     '#4CAF50',
    fontSize:  '0.78rem',
    marginBottom: '0.5rem',
  },
  usersTable: {
    width:          '100%',
    borderCollapse: 'collapse',
    fontSize:       '0.82rem',
  },
  th: {
    padding:       '0.5rem 0.75rem',
    textAlign:     'left',
    color:         C.muted,
    fontSize:      '0.7rem',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    borderBottom:  `1px solid ${C.border}`,
  },
  td: {
    padding:    '0.65rem 0.75rem',
    borderBottom: `1px solid rgba(30,58,95,0.4)`,
    color:      C.text,
    verticalAlign: 'middle',
  },
  mono: {
    fontFamily: "'DM Mono', monospace",
    fontSize:   '0.8rem',
  },
  inactiveRow: {
    opacity: 0.45,
  },
  activeBadge: {
    color:     '#4CAF50',
    fontSize:  '0.75rem',
  },
  inactiveBadge: {
    color:     '#FF6B6B',
    fontSize:  '0.75rem',
  },
  inlineSelect: {
    background:   '#0A1520',
    border:       `1px solid ${C.gold}`,
    borderRadius: 4,
    padding:      '2px 6px',
    color:        C.text,
    fontSize:     '0.78rem',
    fontFamily:   "'DM Mono', monospace",
    outline:      'none',
  },
  loading: {
    color:     C.muted,
    fontSize:  '0.82rem',
    padding:   '1rem 0',
  },
  restricted: {
    color:     C.muted,
    fontSize:  '0.85rem',
    padding:   '2rem',
    textAlign: 'center',
  },
}
