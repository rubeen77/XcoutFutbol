import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import { LigaProvider } from './contexts/LigaContext'
import Navbar from './components/Navbar'
import Footer from './components/Footer'
import Home from './pages/Home'
import Jugador from './pages/Jugador'
import Scouting from './pages/Scouting'
import Insights from './pages/Insights'
import Equipos from './pages/Equipos'
import Partidos from './pages/Partidos'
import Landing from './pages/Landing'

function AppLayout() {
  const location = useLocation()
  return (
    <LigaProvider>
      <div className="min-h-screen bg-slate-950 text-white flex flex-col">
        <Navbar />
        <div key={location.pathname} className="animate-fade-in flex-1">
          <Routes>
            <Route path="/jugadores"    element={<Home />} />
            <Route path="/jugador/:id"  element={<Jugador />} />
            <Route path="/scouting"     element={<Scouting />} />
            <Route path="/equipos"      element={<Equipos />} />
            <Route path="/partidos"     element={<Partidos />} />
            <Route path="/insights"     element={<Insights />} />
          </Routes>
        </div>
        <Footer />
      </div>
    </LigaProvider>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"   element={<Landing />} />
        <Route path="/*"  element={<AppLayout />} />
      </Routes>
    </BrowserRouter>
  )
}
