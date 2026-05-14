import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const CYAN = '#00E5FF'

// ─── Datos de planes ──────────────────────────────────────────────────────────

const PLANES = [
  {
    id:       'gratis',
    nombre:   'Gratis',
    badge:    'Para empezar',
    precioM:  0,
    precioA:  0,
    popular:  false,
    color:    'border-slate-700',
    btnLabel: 'Empezar gratis',
    btnHref:  '/jugadores',
    btnStyle: 'outline',
    features: [
      'Estadísticas completas de jugadores (xG, xA, regates…)',
      'Clasificaciones y resultados',
      'Insights — rankings, quiz, análisis de jornada',
      '5 grandes ligas + Champions League',
      'Cuotas básicas de partidos',
      'Con anuncios',
    ],
  },
  {
    id:       'fan',
    nombre:   'Fan',
    badge:    'Más popular',
    precioM:  2.99,
    precioA:  2.39,
    popular:  true,
    color:    'border-cyan-400',
    btnLabel: 'Empezar 7 días gratis',
    btnHref:  '#',
    btnStyle: 'filled',
    trial:    '7 días gratis — cancela cuando quieras',
    features: [
      'Todo lo del Gratis sin anuncios',
      'Historial por temporada y valor de mercado',
      'Comparador con radar chart',
      'Scouting con algoritmo IA',
      'Buscador avanzado con filtros',
      'Todas las ligas disponibles',
      'Cuotas básicas en todos los partidos',
    ],
  },
  {
    id:       'tipster',
    nombre:   'Tipster',
    badge:    'Beta',
    precioM:  9.99,
    precioA:  7.99,
    popular:  false,
    color:    'border-slate-700',
    btnLabel: 'Empezar 7 días gratis',
    btnHref:  '#',
    btnStyle: 'outline',
    trial:    '7 días gratis — cancela cuando quieras',
    features: [
      'Todo lo del Fan',
      'Tiros a puerta, tarjetas, córners por partido',
      'Rendimiento local/visitante y rachas',
      'Head to head histórico',
      'Análisis pre-partido con IA',
      'Cuotas avanzadas con más mercados',
      'Avisos legales +18 y juego responsable',
    ],
  },
  {
    id:       'club',
    nombre:   'Club',
    badge:    'Para clubes',
    precioM:  null,
    precioA:  null,
    popular:  false,
    color:    'border-slate-700',
    btnLabel: 'Contactar con ventas',
    btnHref:  'mailto:info@xcoutfutbol.com',
    btnStyle: 'outline',
    features: [
      'Todo lo del Fan',
      'Panel de gestión de plantilla propia',
      'Scouting de rivales con informes PDF',
      'Notas privadas por jugador',
      'Soporte prioritario',
      'Factura personalizada',
    ],
  },
]

// ─── Tabla comparativa ────────────────────────────────────────────────────────

const TABLA_FILAS = [
  { label: 'Estadísticas avanzadas (xG, xA…)',      gratis: true,  fan: true,  tipster: true,  club: true  },
  { label: 'Clasificaciones y resultados',            gratis: true,  fan: true,  tipster: true,  club: true  },
  { label: 'Insights — rankings, quiz, análisis IA', gratis: true,  fan: true,  tipster: true,  club: true  },
  { label: 'Sin anuncios',                            gratis: false, fan: true,  tipster: true,  club: true  },
  { label: 'Historial por temporada',                 gratis: false, fan: true,  tipster: true,  club: true  },
  { label: 'Valor de mercado',                        gratis: false, fan: true,  tipster: true,  club: true  },
  { label: 'Comparador con radar chart',              gratis: false, fan: true,  tipster: true,  club: true  },
  { label: 'Scouting IA',                             gratis: false, fan: true,  tipster: true,  club: true  },
  { label: 'Todas las ligas',                         gratis: false, fan: true,  tipster: true,  club: true  },
  { label: 'Tiros a puerta y tarjetas',               gratis: false, fan: false, tipster: true,  club: false },
  { label: 'Head to head histórico',                  gratis: false, fan: false, tipster: true,  club: false },
  { label: 'Análisis pre-partido con IA',             gratis: false, fan: false, tipster: true,  club: false },
  { label: 'Cuotas avanzadas',                        gratis: false, fan: false, tipster: true,  club: false },
  { label: 'Panel de plantilla propia',               gratis: false, fan: false, tipster: false, club: true  },
  { label: 'Informes PDF de rivales',                 gratis: false, fan: false, tipster: false, club: true  },
  { label: 'Notas privadas por jugador',              gratis: false, fan: false, tipster: false, club: true  },
  { label: 'Soporte prioritario',                     gratis: false, fan: false, tipster: false, club: true  },
]

// ─── FAQ ─────────────────────────────────────────────────────────────────────

const FAQS = [
  {
    q: '¿Puedo cancelar cuando quiera?',
    a: 'Sí, sin permanencia ni penalizaciones. Cancela desde tu perfil en cualquier momento.',
  },
  {
    q: '¿Qué pasa cuando termina el trial de 7 días?',
    a: 'Se activa el cobro automático. Te avisamos antes de que termine.',
  },
  {
    q: '¿Los datos son reales?',
    a: 'Sí, todos los datos vienen de FBref, Transfermarkt y Sofascore.',
  },
  {
    q: '¿El tier Tipster incluye consejos de apuestas?',
    a: 'No damos consejos de apuestas. Ofrecemos datos para que tomes tus propias decisiones. Juega con responsabilidad. +18.',
  },
  {
    q: '¿Cómo funciona el tier Club?',
    a: 'Contáctanos y preparamos un plan a medida. Factura mensual sin complicaciones.',
  },
]

// ─── Subcomponentes ───────────────────────────────────────────────────────────

function Check({ ok }) {
  if (ok) return <span className="text-cyan-400 text-base">✓</span>
  return <span className="text-slate-700 text-base">✕</span>
}

function PrecioCard({ plan, anual }) {
  const navigate = useNavigate()
  const precio = anual ? plan.precioA : plan.precioM

  function handleClick(e) {
    if (plan.btnHref === '/jugadores') { e.preventDefault(); navigate('/jugadores') }
    else if (plan.btnHref.startsWith('mailto:')) { /* abre cliente mail */ }
  }

  return (
    <div className={`relative flex flex-col rounded-2xl border bg-slate-900 p-6
                     transition-all duration-200 hover:border-cyan-500/40
                     ${plan.popular ? 'border-cyan-400 shadow-lg shadow-cyan-500/10' : 'border-slate-800'}`}>

      {plan.popular && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="bg-cyan-400 text-slate-950 text-[10px] font-black uppercase tracking-widest
                           px-3 py-1 rounded-full">
            Más popular
          </span>
        </div>
      )}

      {/* Badge */}
      <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">
        {plan.badge}
      </span>

      {/* Nombre */}
      <h3 className={`text-xl font-black mb-4 ${plan.popular ? 'text-cyan-400' : 'text-white'}`}>
        {plan.nombre}
      </h3>

      {/* Precio */}
      <div className="mb-5">
        {precio === null ? (
          <p className="text-2xl font-black text-white">A medida</p>
        ) : precio === 0 ? (
          <p className="text-4xl font-black text-white">Gratis</p>
        ) : (
          <div className="flex items-end gap-1">
            <span className="text-4xl font-black text-white">{precio.toFixed(2).replace('.', ',')}€</span>
            <span className="text-slate-500 text-sm mb-1">/mes</span>
          </div>
        )}
        {anual && precio > 0 && (
          <p className="text-xs text-cyan-400 font-semibold mt-1">Facturado anualmente · 20% dto.</p>
        )}
      </div>

      {/* Trial */}
      {plan.trial && (
        <p className="text-xs text-emerald-400 font-semibold mb-4">{plan.trial}</p>
      )}

      {/* Botón */}
      <a
        href={plan.btnHref}
        onClick={handleClick}
        className={`w-full text-center py-2.5 rounded-xl text-sm font-bold transition-all duration-150 mb-6
          ${plan.btnStyle === 'filled'
            ? 'bg-cyan-400 text-slate-950 hover:bg-cyan-300'
            : 'border border-slate-700 text-slate-300 hover:border-cyan-500/50 hover:text-white'}`}
      >
        {plan.btnLabel}
      </a>

      {/* Features */}
      <ul className="space-y-2.5 flex-1">
        {plan.features.map(f => (
          <li key={f} className="flex items-start gap-2 text-sm text-slate-400">
            <span className="text-cyan-400 shrink-0 mt-0.5">✓</span>
            {f}
          </li>
        ))}
      </ul>
    </div>
  )
}

function FaqItem({ q, a }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border-b border-slate-800 last:border-0">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between gap-4 py-4 text-left
                   text-sm font-semibold text-white hover:text-cyan-400 transition-colors"
      >
        {q}
        <span className={`shrink-0 text-slate-500 transition-transform duration-200 ${open ? 'rotate-45' : ''}`}>+</span>
      </button>
      {open && (
        <p className="pb-4 text-sm text-slate-400 leading-relaxed">{a}</p>
      )}
    </div>
  )
}

// ─── Página ───────────────────────────────────────────────────────────────────

export default function Precios() {
  const [anual, setAnual] = useState(false)

  return (
    <main className="min-h-screen bg-[#080C10] text-white">
      <div className="max-w-6xl mx-auto px-4 py-14 space-y-20">

        {/* ── Cabecera ── */}
        <div className="text-center space-y-5">
          <h1 className="text-4xl font-black tracking-tight">Elige tu plan</h1>
          <p className="text-slate-400 text-lg">Empieza gratis. Sube cuando quieras.</p>

          {/* Toggle */}
          <div className="inline-flex items-center gap-3 bg-slate-900 border border-slate-800 rounded-full px-5 py-2.5">
            <button
              onClick={() => setAnual(false)}
              className={`text-sm font-semibold transition-colors ${!anual ? 'text-white' : 'text-slate-500 hover:text-slate-300'}`}
            >
              Mensual
            </button>
            <button
              onClick={() => setAnual(v => !v)}
              className={`relative w-10 h-5 rounded-full transition-colors duration-200 shrink-0
                          ${anual ? 'bg-cyan-400' : 'bg-slate-700'}`}
            >
              <span className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200
                                ${anual ? 'translate-x-5' : 'translate-x-0'}`} />
            </button>
            <button
              onClick={() => setAnual(true)}
              className={`text-sm font-semibold transition-colors ${anual ? 'text-white' : 'text-slate-500 hover:text-slate-300'}`}
            >
              Anual
              <span className="ml-1.5 text-[10px] font-black text-cyan-400 bg-cyan-400/10 border border-cyan-400/30 rounded-full px-1.5 py-0.5">
                −20%
              </span>
            </button>
          </div>
        </div>

        {/* ── Cards ── */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {PLANES.map(plan => (
            <PrecioCard key={plan.id} plan={plan} anual={anual} />
          ))}
        </div>

        {/* ── Tabla comparativa ── */}
        <section>
          <h2 className="text-xl font-black text-white mb-6 text-center">Comparativa completa</h2>
          <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800">
                  <th className="text-left px-5 py-4 text-slate-500 font-semibold w-1/2">Función</th>
                  {PLANES.map(p => (
                    <th key={p.id} className={`px-4 py-4 text-center font-black
                      ${p.popular ? 'text-cyan-400' : 'text-slate-400'}`}>
                      {p.nombre}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {TABLA_FILAS.map((fila, i) => (
                  <tr key={i} className="border-b border-slate-800/50 last:border-0 hover:bg-slate-800/20 transition-colors">
                    <td className="px-5 py-3 text-slate-400">{fila.label}</td>
                    <td className="px-4 py-3 text-center"><Check ok={fila.gratis}  /></td>
                    <td className="px-4 py-3 text-center"><Check ok={fila.fan}     /></td>
                    <td className="px-4 py-3 text-center"><Check ok={fila.tipster} /></td>
                    <td className="px-4 py-3 text-center"><Check ok={fila.club}    /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* ── FAQ ── */}
        <section>
          <h2 className="text-xl font-black text-white mb-6 text-center">Preguntas frecuentes</h2>
          <div className="max-w-2xl mx-auto bg-slate-900 border border-slate-800 rounded-2xl px-6">
            {FAQS.map(f => <FaqItem key={f.q} q={f.q} a={f.a} />)}
          </div>
        </section>

        {/* ── Aviso legal ── */}
        <p className="text-center text-xs text-slate-700">
          +18 | Juega con responsabilidad | Las apuestas pueden causar adicción
        </p>

      </div>
    </main>
  )
}
