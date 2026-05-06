import { createContext, useContext, useState, useEffect } from 'react'
import { getLeagues } from '../services/api'

const LigaContext = createContext(null)

// Emoji por liga_id — se añade aquí cuando llega una liga nueva
const EMOJI_MAP = {
  1:  '🇪🇸',
  24: '🏴󠁧󠁢󠁥󠁮󠁧󠁿',
  25: '🇩🇪',
  26: '🇮🇹',
  27: '🇫🇷',
}

const FALLBACK_LIGAS = [
  { id: 1,  nombre: 'LaLiga',         pais: 'España',     emoji: '🇪🇸' },
  { id: 24, nombre: 'Premier League', pais: 'Inglaterra', emoji: '🏴󠁧󠁢󠁥󠁮󠁧󠁿' },
  { id: 25, nombre: 'Bundesliga',     pais: 'Alemania',   emoji: '🇩🇪' },
]

function enrichLiga(liga) {
  return { ...liga, emoji: EMOJI_MAP[liga.id] ?? '🏆' }
}

export function LigaProvider({ children }) {
  const [ligaId, setLigaId] = useState(1)
  const [ligas,  setLigas]  = useState(FALLBACK_LIGAS)

  useEffect(() => {
    getLeagues()
      .then(data => {
        const fetched = (data.ligas || []).map(enrichLiga)
        if (fetched.length > 0) setLigas(fetched)
      })
      .catch(() => {
        // Backend no disponible — usar fallback
      })
  }, [])

  const ligaActual = ligas.find(l => l.id === ligaId) ?? ligas[0]

  return (
    <LigaContext.Provider value={{ ligaId, setLigaId, ligaActual, ligas }}>
      {children}
    </LigaContext.Provider>
  )
}

export function useLiga() {
  return useContext(LigaContext)
}
