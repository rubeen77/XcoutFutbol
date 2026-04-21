import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom'
import Navbar from './components/Navbar'
import Footer from './components/Footer'
import Home from './pages/Home'
import Jugador from './pages/Jugador'
import Scouting from './pages/Scouting'
import Insights from './pages/Insights'
import Equipos from './pages/Equipos'
import Partidos from './pages/Partidos'

function AnimatedRoutes() {
  const location = useLocation()
  return (
    <div key={location.pathname} className="animate-fade-in flex-1">
      <Routes location={location}>
        <Route path="/"            element={<Home />} />
        <Route path="/jugador/:id" element={<Jugador />} />
        <Route path="/scouting"    element={<Scouting />} />
        <Route path="/equipos"     element={<Equipos />} />
        <Route path="/partidos"    element={<Partidos />} />
        <Route path="/insights"    element={<Insights />} />
      </Routes>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-950 text-white flex flex-col">
        <Navbar />
        <AnimatedRoutes />
        <Footer />
      </div>
    </BrowserRouter>
  )
}
