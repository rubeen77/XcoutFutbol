import { Link } from 'react-router-dom'

function FooterLogo() {
  return (
    <svg viewBox="0 0 40 40" className="w-6 h-6" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="fg1" x1="11" y1="11" x2="29" y2="29" gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#22d3ee" stopOpacity="0.55" />
          <stop offset="50%"  stopColor="#ffffff"  stopOpacity="1" />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.55" />
        </linearGradient>
        <linearGradient id="fg2" x1="29" y1="11" x2="11" y2="29" gradientUnits="userSpaceOnUse">
          <stop offset="0%"   stopColor="#22d3ee" stopOpacity="0.55" />
          <stop offset="50%"  stopColor="#ffffff"  stopOpacity="1" />
          <stop offset="100%" stopColor="#22d3ee" stopOpacity="0.55" />
        </linearGradient>
      </defs>
      <circle cx="20" cy="20" r="17.5"
        stroke="#22d3ee" strokeWidth="0.7" strokeOpacity="0.15"
        strokeDasharray="3 4" fill="none" />
      <line x1="11.5" y1="11.5" x2="28.5" y2="28.5"
        stroke="url(#fg1)" strokeWidth="1.9" strokeLinecap="round" />
      <line x1="28.5" y1="11.5" x2="11.5" y2="28.5"
        stroke="url(#fg2)" strokeWidth="1.9" strokeLinecap="round" />
      <circle cx="20" cy="20" r="1.2" fill="white" fillOpacity="0.9" />
    </svg>
  )
}

export default function Footer() {
  return (
    <footer className="border-t border-slate-800/60 bg-slate-950 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-7">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">

          {/* Brand */}
          <div className="flex items-center gap-3">
            <FooterLogo />
            <div className="flex items-center gap-2">
              <span
                className="text-sm font-black tracking-tight select-none"
                style={{ letterSpacing: '-0.03em' }}
              >
                <span
                  className="text-cyan-400"
                  style={{ textShadow: '0 0 12px rgba(34,211,238,0.45)' }}
                >
                  X
                </span>
                <span className="text-white font-semibold">cout</span>
              </span>
              <span className="text-slate-700 text-xs">·</span>
              <span className="text-slate-600 text-xs">© 2026</span>
            </div>
          </div>

          {/* Links */}
          <nav className="flex items-center gap-5 text-xs text-slate-600">
            <a href="#" className="hover:text-slate-400 transition-colors">Términos de uso</a>
            <a href="#" className="hover:text-slate-400 transition-colors">Privacidad</a>
            <span className="text-slate-800">·</span>
            <span className="text-slate-700">LaLiga 2025/26</span>
          </nav>

        </div>
      </div>
    </footer>
  )
}
