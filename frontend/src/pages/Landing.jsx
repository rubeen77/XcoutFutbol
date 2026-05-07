import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
)

const RESEND_KEY = import.meta.env.VITE_RESEND_API_KEY

function XcoutLogo() {
  return (
    <svg viewBox="0 0 40 40" width="36" height="36" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="lxg1" x1="11" y1="11" x2="29" y2="29" gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#22d3ee" stopOpacity="0.55" />
          <stop offset="48%"  stopColor="#e0faff" stopOpacity="1" />
          <stop offset="52%"  stopColor="#ffffff"  stopOpacity="1" />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.55" />
        </linearGradient>
        <linearGradient id="lxg2" x1="29" y1="11" x2="11" y2="29" gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#22d3ee" stopOpacity="0.55" />
          <stop offset="48%"  stopColor="#e0faff" stopOpacity="1" />
          <stop offset="52%"  stopColor="#ffffff"  stopOpacity="1" />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.55" />
        </linearGradient>
        <radialGradient id="lxglow" cx="50%" cy="50%" r="50%">
          <stop offset="0%"   stopColor="#ffffff"  stopOpacity="0.85" />
          <stop offset="45%"  stopColor="#67e8f9"  stopOpacity="0.25" />
          <stop offset="100%" stopColor="#22d3ee"  stopOpacity="0" />
        </radialGradient>
      </defs>
      <circle cx="20" cy="20" r="17.5" stroke="#22d3ee" strokeWidth="0.7" strokeOpacity="0.18" strokeDasharray="3.5 4.5" fill="none" />
      <circle cx="20" cy="20" r="11.5" stroke="#22d3ee" strokeWidth="0.5" strokeOpacity="0.09" fill="none" />
      <line x1="11.5" y1="11.5" x2="28.5" y2="28.5" stroke="url(#lxg1)" strokeWidth="1.9" strokeLinecap="round" />
      <line x1="28.5" y1="11.5" x2="11.5" y2="28.5" stroke="url(#lxg2)" strokeWidth="1.9" strokeLinecap="round" />
      <circle cx="20" cy="20" r="5.5" fill="url(#lxglow)" />
      <circle cx="20" cy="20" r="1.3" fill="white" fillOpacity="0.92" />
    </svg>
  )
}

const ACCENT = '#00E5FF'
const BG       = '#080C10'

const STATS = [
  { num: '10.000+', label: 'jugadores' },
  { num: '20+',     label: 'ligas' },
  { num: '5.000+',  label: 'partidos' },
  { num: '100%',    label: 'en español' },
]

const FEATURES = [
  {
    icon: '📊',
    title: 'Estadísticas avanzadas con IA',
    desc:  'xG, xA, radar charts y métricas que solo tenían los clubes profesionales. Ahora al alcance de cualquiera.',
  },
  {
    icon: '🔍',
    title: 'Scouting inteligente',
    desc:  'Compara jugadores de cualquier liga y encuentra similares con algoritmos de IA.',
  },
  {
    icon: '🤖',
    title: 'Análisis narrativo automático',
    desc:  'Cada jornada, un análisis periodístico generado por IA con los datos más llamativos.',
  },
]

function StatCard({ num, label }) {
  return (
    <div style={{
      background:   'rgba(0,229,255,0.04)',
      border:       '1px solid rgba(0,229,255,0.13)',
      borderRadius: 12,
      padding:      '1rem 1.25rem',
    }}>
      <div style={{ fontSize: '1.65rem', fontWeight: 900, color: ACCENT, letterSpacing: '-0.04em', lineHeight: 1 }}>
        {num}
      </div>
      <div style={{ fontSize: '0.72rem', color: 'rgba(255,255,255,0.4)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em', marginTop: 5 }}>
        {label}
      </div>
    </div>
  )
}

function FeatureCard({ icon, title, desc }) {
  return (
    <div style={{
      background:   'rgba(255,255,255,0.025)',
      border:       '1px solid rgba(255,255,255,0.07)',
      borderRadius: 16,
      padding:      '1.75rem',
    }}>
      <div style={{ fontSize: '1.7rem', marginBottom: '0.9rem' }}>{icon}</div>
      <h3 style={{ fontWeight: 800, fontSize: '1rem', marginBottom: '0.5rem', letterSpacing: '-0.02em' }}>
        {title}
      </h3>
      <p style={{ color: 'rgba(255,255,255,0.38)', fontSize: '0.875rem', lineHeight: 1.65, margin: 0 }}>
        {desc}
      </p>
    </div>
  )
}

export default function Landing() {
  const navigate = useNavigate()
  const [email,    setEmail]    = useState('')
  const [focused,  setFocused]  = useState(false)
  const [status,   setStatus]   = useState('idle') // idle | loading | success | error
  const [errorMsg, setErrorMsg] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    const cleaned = email.trim()
    if (!cleaned) return
    setStatus('loading')
    setErrorMsg('')

    try {
      // 1. Guardar en Supabase (ignora duplicados por la constraint unique de email)
      const { error: dbError } = await supabase
        .from('lista_espera')
        .upsert({ email: cleaned, origen: 'landing' }, { onConflict: 'email', ignoreDuplicates: true })

      if (dbError) throw new Error(dbError.message)

      // 2. Email de confirmación al usuario
      await _sendEmail({
        to:      [cleaned],
        subject: '¡Ya estás en la lista de espera de Xcout! 🚀',
        html:    confirmationHtml(cleaned),
      })

      // 3. Notificación interna (best-effort, no bloquea)
      _sendEmail({
        to:      ['info@xcoutfutbol.com'],
        subject: `Nuevo registro en lista de espera: ${cleaned}`,
        html:    `<p>Nuevo email en lista de espera: <strong>${cleaned}</strong></p>`,
      }).catch(() => {})

      setStatus('success')
    } catch (err) {
      setErrorMsg(err.message || 'Error al registrarse. Inténtalo de nuevo.')
      setStatus('error')
    }
  }

  async function _sendEmail({ to, subject, html }) {
    if (!RESEND_KEY) return
    const res = await fetch('https://api.resend.com/emails', {
      method:  'POST',
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${RESEND_KEY}`,
      },
      body: JSON.stringify({ from: 'Xcout <info@xcoutfutbol.com>', to, subject, html }),
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.message || `Resend error ${res.status}`)
    }
  }

  return (
    <div style={{ background: BG, minHeight: '100vh', color: '#fff', fontFamily: 'inherit' }}>

      {/* ── Navbar ─────────────────────────────────────────────────────── */}
      <nav style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{
          maxWidth: 1160, margin: '0 auto', padding: '0 1.5rem',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 64,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <XcoutLogo />
            <span style={{ fontSize: '1.2rem', fontWeight: 900, letterSpacing: '-0.03em', lineHeight: 1 }}>
              <span style={{ color: '#22d3ee', textShadow: '0 0 18px rgba(34,211,238,0.55), 0 0 6px rgba(34,211,238,0.3)' }}>X</span>
              <span style={{ color: '#fff', fontWeight: 600, letterSpacing: '-0.01em' }}>cout</span>
            </span>
          </div>
        </div>
      </nav>

      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <section className="landing-hero" style={{ maxWidth: 1160, margin: '0 auto', padding: '5.5rem 1.5rem 3.5rem' }}>

        {/* Left col */}
        <div>
          <h1 style={{
            fontSize: 'clamp(2.4rem, 5vw, 3.75rem)',
            fontWeight: 900, lineHeight: 1.08, letterSpacing: '-0.045em',
            margin: '0 0 1.4rem',
          }}>
            El fútbol<br />
            en datos<br />
            <span style={{ color: ACCENT }}>reales.</span>
          </h1>

          <p style={{
            fontSize: '1.05rem', color: 'rgba(255,255,255,0.5)', lineHeight: 1.72,
            margin: '0 0 2.4rem', maxWidth: 460,
          }}>
            Estadísticas avanzadas, scouting inteligente y análisis generados
            con IA. Para amantes del fútbol, tipsters y clubes que quieren
            datos de calidad sin pagar precios de élite. En español.
          </p>

          <div className="landing-stats">
            {STATS.map(s => <StatCard key={s.label} {...s} />)}
          </div>
        </div>

        {/* Right col – waitlist */}
        <div style={{
          background:   'rgba(255,255,255,0.03)',
          border:       '1px solid rgba(255,255,255,0.08)',
          borderRadius: 20,
          padding:      '2.4rem 2rem',
        }}>
          <span style={{
            display: 'inline-block',
            background:    `${ACCENT}18`,
            border:        `1px solid ${ACCENT}33`,
            color:         ACCENT,
            fontSize:      '0.68rem',
            fontWeight:    800,
            letterSpacing: '0.13em',
            textTransform: 'uppercase',
            padding:       '0.3rem 0.85rem',
            borderRadius:  999,
            marginBottom:  '1.4rem',
          }}>
            Acceso anticipado
          </span>

          <h2 style={{ fontSize: '1.55rem', fontWeight: 900, lineHeight: 1.2, letterSpacing: '-0.03em', margin: '0 0 0.5rem' }}>
            Sé el primero en entrar cuando lancemos.
          </h2>
          <p style={{ color: ACCENT, fontSize: '0.82rem', fontWeight: 600, margin: '0 0 0.8rem' }}>
            🚀 Lanzamiento previsto: junio 2026
          </p>
          <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.88rem', margin: '0 0 1.8rem', lineHeight: 1.65 }}>
            Únete a la lista y te avisamos en el momento del lanzamiento.
          </p>

          {status === 'success' ? (
            <div style={{
              background:   `${ACCENT}0d`,
              border:       `1px solid ${ACCENT}40`,
              borderRadius: 12,
              padding:      '1.5rem',
              textAlign:    'center',
            }}>
              <div style={{ fontSize: '2rem', marginBottom: '0.4rem' }}>🎉</div>
              <div style={{ fontWeight: 700, color: ACCENT, marginBottom: '0.2rem' }}>¡Ya estás en la lista!</div>
              <div style={{ fontSize: '0.82rem', color: 'rgba(255,255,255,0.38)' }}>Te avisaremos cuando lancemos.</div>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <input
                type="email"
                required
                placeholder="tu@email.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                style={{
                  width:        '100%',
                  boxSizing:    'border-box',
                  background:   'rgba(255,255,255,0.05)',
                  border:       `1px solid ${focused ? `${ACCENT}55` : 'rgba(255,255,255,0.1)'}`,
                  borderRadius: 10,
                  padding:      '0.85rem 1rem',
                  color:        '#fff',
                  fontSize:     '0.93rem',
                  outline:      'none',
                  marginBottom: '0.7rem',
                  transition:   'border-color 0.15s',
                }}
              />

              {status === 'error' && (
                <p style={{ color: '#ff6b6b', fontSize: '0.78rem', margin: '0 0 0.6rem' }}>
                  {errorMsg}
                </p>
              )}

              <button
                type="submit"
                disabled={status === 'loading'}
                style={{
                  width:        '100%',
                  background:   ACCENT,
                  color:        BG,
                  border:       'none',
                  borderRadius: 10,
                  padding:      '0.88rem 1rem',
                  fontWeight:   800,
                  fontSize:     '0.92rem',
                  cursor:       status === 'loading' ? 'wait' : 'pointer',
                  opacity:      status === 'loading' ? 0.7 : 1,
                  transition:   'opacity 0.15s',
                  letterSpacing: '-0.01em',
                }}
              >
                {status === 'loading' ? 'Enviando…' : 'Unirme a la lista de espera →'}
              </button>

              <p style={{ textAlign: 'center', fontSize: '0.72rem', color: 'rgba(255,255,255,0.2)', margin: '0.7rem 0 0' }}>
                Sin spam, te lo prometemos. Solo te avisaremos cuando haya novedades importantes sobre Xcout.
              </p>
            </form>
          )}
        </div>
      </section>

      {/* ── Features ───────────────────────────────────────────────────── */}
      <section style={{ maxWidth: 1160, margin: '0 auto', padding: '0 1.5rem 5rem' }}>
        <div className="landing-features">
          {FEATURES.map(f => <FeatureCard key={f.title} {...f} />)}
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <footer style={{ borderTop: '1px solid rgba(255,255,255,0.06)', padding: '1.5rem', textAlign: 'center' }}>
        <p style={{ color: 'rgba(255,255,255,0.18)', fontSize: '0.78rem', margin: '0 0 0.35rem' }}>
          ✕ Xcout · xcoutfutbol.com · © 2026
        </p>
        <p style={{ color: 'rgba(255,255,255,0.18)', fontSize: '0.72rem', margin: '0 0 0.6rem' }}>
          Contacto:{' '}
          <a
            href="mailto:info@xcoutfutbol.com"
            style={{ color: 'rgba(255,255,255,0.28)', textDecoration: 'underline', textUnderlineOffset: 3 }}
          >
            info@xcoutfutbol.com
          </a>
        </p>
        <HiddenEnterButton onClick={() => navigate('/jugadores')} />
      </footer>

      {/* ── Responsive CSS ─────────────────────────────────────────────── */}
      <style>{`
        .landing-hero {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 4rem;
          align-items: center;
        }
        .landing-stats {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 0.85rem;
        }
        .landing-features {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 1.25rem;
        }
        @media (max-width: 768px) {
          .landing-hero {
            grid-template-columns: 1fr;
            gap: 2.5rem;
          }
          .landing-features {
            grid-template-columns: 1fr;
          }
        }
        @media (max-width: 480px) {
          .landing-stats {
            grid-template-columns: 1fr 1fr;
          }
        }
      `}</style>
    </div>
  )
}

function HiddenEnterButton({ onClick }) {
  const [hover, setHover] = useState(false)
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display:      'inline-flex',
        alignItems:   'center',
        justifyContent: 'center',
        width:        28,
        height:       28,
        borderRadius: '50%',
        background:   hover ? 'rgba(255,255,255,0.05)' : 'none',
        border:       'none',
        color:        hover ? '#666' : '#333',
        fontSize:     11,
        cursor:       'pointer',
        transition:   'color 0.2s, background 0.2s',
        userSelect:   'none',
        marginTop:    4,
      }}
      title="Entrar"
    >
      ✕
    </button>
  )
}

function confirmationHtml(email) {
  return `<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#080C10;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#ffffff;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#080C10;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#0d1520;border:1px solid rgba(255,255,255,0.08);border-radius:16px;overflow:hidden;">
        <tr><td style="background:linear-gradient(135deg,#0d1f30 0%,#080C10 100%);padding:36px 40px 28px;border-bottom:1px solid rgba(0,229,255,0.15);">
          <p style="margin:0;font-size:26px;font-weight:900;letter-spacing:-0.04em;">
            <span style="color:#00E5FF;">X</span><span style="color:#fff;font-weight:600;">cout</span>
          </p>
          <p style="margin:8px 0 0;font-size:11px;color:rgba(255,255,255,0.3);letter-spacing:0.12em;text-transform:uppercase;">Football Analytics</p>
        </td></tr>
        <tr><td style="padding:36px 40px;">
          <p style="margin:0 0 8px;font-size:22px;font-weight:800;letter-spacing:-0.03em;">¡Ya estás en la lista! 🎉</p>
          <p style="margin:0 0 24px;font-size:14px;color:rgba(255,255,255,0.45);line-height:1.7;">
            Hola, gracias por apuntarte a la lista de espera de Xcout.<br>
            Te avisaremos en cuanto abramos el acceso.
          </p>
          <div style="background:rgba(0,229,255,0.06);border:1px solid rgba(0,229,255,0.2);border-radius:10px;padding:16px 20px;margin-bottom:28px;">
            <p style="margin:0;font-size:13px;color:#00E5FF;font-weight:700;">🚀 Lanzamiento previsto: junio 2026</p>
          </div>
          <p style="margin:0 0 14px;font-size:12px;font-weight:700;color:rgba(255,255,255,0.3);text-transform:uppercase;letter-spacing:0.1em;">Qué encontrarás en Xcout</p>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr><td style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
              <span style="color:#00E5FF;">📊</span>&nbsp;&nbsp;
              <span style="font-size:13px;color:rgba(255,255,255,0.7);">Estadísticas avanzadas con IA — xG, xA, radar charts</span>
            </td></tr>
            <tr><td style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.05);">
              <span style="color:#00E5FF;">🔍</span>&nbsp;&nbsp;
              <span style="font-size:13px;color:rgba(255,255,255,0.7);">Scouting inteligente con algoritmos de similitud</span>
            </td></tr>
            <tr><td style="padding:8px 0;">
              <span style="color:#00E5FF;">🤖</span>&nbsp;&nbsp;
              <span style="font-size:13px;color:rgba(255,255,255,0.7);">Análisis narrativo automático de cada jornada</span>
            </td></tr>
          </table>
        </td></tr>
        <tr><td style="padding:20px 40px;border-top:1px solid rgba(255,255,255,0.06);">
          <p style="margin:0;font-size:11px;color:rgba(255,255,255,0.2);line-height:1.6;">
            ✕ Xcout · xcoutfutbol.com<br>
            Contacto: <a href="mailto:info@xcoutfutbol.com" style="color:rgba(255,255,255,0.3);">info@xcoutfutbol.com</a><br>
            Sin spam, te lo prometemos. Solo te avisaremos cuando haya novedades importantes.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>`
}
