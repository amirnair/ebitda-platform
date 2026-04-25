/**
 * companyConfig.js
 * ─────────────────────────────────────────────────────────────────────────────
 * AC Industries — pilot client configuration.
 *
 * ARCHITECTURE NOTE (multi-tenant SaaS):
 *   In production this object is fetched from the /companies/{company_id}
 *   endpoint on app boot and stored in CompanyContext. Nothing in the UI
 *   hardcodes client-specific values — it always reads from this config.
 *
 *   Adding a new client = new row in the companies table + new config object.
 *   No UI code changes required.
 * ─────────────────────────────────────────────────────────────────────────────
 */

const AC_INDUSTRIES_CONFIG = {
  company_id: "AC001",
  company_name: "AC Industries",
  logo_url: null,                    // null → show text initials "AC"

  // ── Branding ───────────────────────────────────────────────────────────────
  // primary_colour drives: sidebar accent, active nav state, KPI highlights,
  // chart primary series, gauge fills.
  // secondary_colour drives: forecast line, success states, cycle health gauges.
  primary_colour: "#185FA5",         // deep blue — pulled from here everywhere
  secondary_colour: "#0F6E56",       // deep teal

  // Derived lighter tints used for fills (auto-computed in theme.js but
  // defined here as fallbacks for components that can't import theme).
  primary_colour_light: "#E6F1FB",
  secondary_colour_light: "#E1F5EE",

  // ── Locale & finance ──────────────────────────────────────────────────────
  currency: "INR",
  currency_symbol: "₹",
  fiscal_year_start_month: 4,        // April
  timezone: "Asia/Kolkata",

  // ── Brand / product names ─────────────────────────────────────────────────
  brand_1: {
    code: "P1",
    name: "Product 1",
    grade: "Fe 550",
    role: "Growth Brand",
    colour: "#185FA5",               // matches primary_colour
    colour_light: "#E6F1FB",
  },
  brand_2: {
    code: "P2",
    name: "Product 2",
    grade: "Fe 550",
    role: "Established Brand",
    colour: "#BA7517",
    colour_light: "#FAEEDA",
  },

  // ── SKU master ────────────────────────────────────────────────────────────
  skus: [
    { code: "P1-SKU-8",  brand: "P1", size_mm: 8,  billet_type: "P1-6M",    billet_length: 6.0  },
    { code: "P1-SKU-10", brand: "P1", size_mm: 10, billet_type: "P1-6M",    billet_length: 6.0  },
    { code: "P1-SKU-12", brand: "P1", size_mm: 12, billet_type: "P1-6M",    billet_length: 6.0  },
    { code: "P1-SKU-16", brand: "P1", size_mm: 16, billet_type: "P1-6M",    billet_length: 6.0  },
    { code: "P1-SKU-20", brand: "P1", size_mm: 20, billet_type: "P1-6M",    billet_length: 6.0  },
    { code: "P1-SKU-25", brand: "P1", size_mm: 25, billet_type: "P1-5.6M",  billet_length: 5.6  },
    { code: "P1-SKU-32", brand: "P1", size_mm: 32, billet_type: "P1-5.05M", billet_length: 5.05 },
    { code: "P2-SKU-8",  brand: "P2", size_mm: 8,  billet_type: "P2-6M",    billet_length: 6.0  },
    { code: "P2-SKU-10", brand: "P2", size_mm: 10, billet_type: "P2-6M",    billet_length: 6.0  },
    { code: "P2-SKU-12", brand: "P2", size_mm: 12, billet_type: "P2-6M",    billet_length: 6.0  },
    { code: "P2-SKU-16", brand: "P2", size_mm: 16, billet_type: "P2-6M",    billet_length: 6.0  },
    { code: "P2-SKU-20", brand: "P2", size_mm: 20, billet_type: "P2-6M",    billet_length: 6.0  },
    { code: "P2-SKU-25", brand: "P2", size_mm: 25, billet_type: "P2-5.6M",  billet_length: 5.6  },
    { code: "P2-SKU-32", brand: "P2", size_mm: 32, billet_type: "P2-4.9M",  billet_length: 4.9  },
  ],

  // ── Production parameters ─────────────────────────────────────────────────
  rolling_factor: 1.05,
  changeover_hours: 2,
  standard_mill_runtime_hours: 16,
  // Mill capacity by size band (MT/hr)
  mill_capacity: {
    8: 18, 10: 19, 12: 20, 16: 21, 20: 22, 25: 23, 32: 25,
  },

  // ── EBITDA benchmarks (client-overridable) ────────────────────────────────
  benchmarks: {
    power_units_per_hr: 280,
    power_rate_inr_per_unit: 7.2,
    fuel_cost_per_hr_inr: 850,
    electrode_cost_per_ton: 180,
    labour_cost_per_ton: 220,
  },

  // ── User / roles ──────────────────────────────────────────────────────────
  current_user: {
    name: "Founder",
    role: "owner",                   // owner | manager | viewer | production | sales
    email: "founder@acindustries.in",
  },
};

export default AC_INDUSTRIES_CONFIG;
