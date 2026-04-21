import { useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts'

/* ══════════════════════════════════════════════════════
   HELPERS
══════════════════════════════════════════════════════ */
function initials(nombre) {
  return nombre.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
}
function notaColor(nota) {
  if (nota >= 8.5) return '#22d3ee'
  if (nota >= 7.5) return '#4ade80'
  if (nota >= 6.5) return '#fbbf24'
  return '#f87171'
}

/* ══════════════════════════════════════════════════════
   DATA — Jornada 35 LaLiga 2024/25
══════════════════════════════════════════════════════ */
const PARTIDOS = [
  {
    id: 1,
    local:     { nombre: 'Real Madrid',  abrev: 'RMA', color: '#22d3ee' },
    visitante: { nombre: 'FC Barcelona', abrev: 'BAR', color: '#a78bfa' },
    resultado: { local: 3, visitante: 1 },
    fecha: '19 Abr 2025', hora: '21:00', estado: 'jugado',
    estadio: 'Santiago Bernabéu',
    xG: { local: 2.84, visitante: 1.21 },
    stats: {
      posesion:    { local: 48, visitante: 52 },
      tirosTotal:  { local: 14, visitante: 10 },
      tirosPuerta: { local: 7,  visitante: 4  },
      corners:     { local: 6,  visitante: 3  },
      faltas:      { local: 11, visitante: 15 },
      amarillas:   { local: 2,  visitante: 3  },
      rojas:       { local: 0,  visitante: 1  },
      fuerasJuego: { local: 3,  visitante: 2  },
    },
    timeline: [
      { min: 23, tipo: 'gol',         equipo: 'local',     jugador: 'Vinicius Jr.' },
      { min: 41, tipo: 'amarilla',    equipo: 'visitante', jugador: 'Araujo' },
      { min: 55, tipo: 'gol',         equipo: 'local',     jugador: 'Bellingham' },
      { min: 58, tipo: 'amarilla',    equipo: 'local',     jugador: 'Rüdiger' },
      { min: 67, tipo: 'gol',         equipo: 'visitante', jugador: 'Lewandowski' },
      { min: 75, tipo: 'gol',         equipo: 'local',     jugador: 'Vinicius Jr.' },
      { min: 78, tipo: 'roja',        equipo: 'visitante', jugador: 'Araujo' },
      { min: 80, tipo: 'sustitucion', equipo: 'local',     jugador: 'Camavinga',   jugadorOut: 'Bellingham' },
      { min: 85, tipo: 'sustitucion', equipo: 'visitante', jugador: 'F. Torres',   jugadorOut: 'Raphinha' },
    ],
    xgTimeline: [
      { min: 0,  local: 0,    visitante: 0    },
      { min: 15, local: 0.18, visitante: 0.09 },
      { min: 23, local: 0.72, visitante: 0.15 },
      { min: 30, local: 0.88, visitante: 0.31 },
      { min: 45, local: 1.12, visitante: 0.59 },
      { min: 55, local: 1.74, visitante: 0.71 },
      { min: 67, local: 1.91, visitante: 1.21 },
      { min: 75, local: 2.84, visitante: 1.21 },
      { min: 90, local: 2.84, visitante: 1.21 },
    ],
    disparos: [
      { x: 82, y: 30, tipo: 'gol',    equipo: 'local' },
      { x: 78, y: 36, tipo: 'gol',    equipo: 'local' },
      { x: 88, y: 32, tipo: 'gol',    equipo: 'local' },
      { x: 75, y: 27, tipo: 'parado', equipo: 'local' },
      { x: 70, y: 38, tipo: 'parado', equipo: 'local' },
      { x: 72, y: 21, tipo: 'fuera',  equipo: 'local' },
      { x: 65, y: 44, tipo: 'fuera',  equipo: 'local' },
      { x: 18, y: 32, tipo: 'gol',    equipo: 'visitante' },
      { x: 22, y: 27, tipo: 'parado', equipo: 'visitante' },
      { x: 25, y: 38, tipo: 'parado', equipo: 'visitante' },
      { x: 30, y: 21, tipo: 'fuera',  equipo: 'visitante' },
      { x: 28, y: 44, tipo: 'fuera',  equipo: 'visitante' },
    ],
    jugadores: [
      { nombre: 'Courtois',     pos: 'POR', equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 8.1 },
      { nombre: 'Vinicius Jr.', pos: 'EI',  equipo: 'local',     mins: 90, goles: 2, asis: 1, xG: 1.41, nota: 9.2 },
      { nombre: 'Bellingham',   pos: 'MC',  equipo: 'local',     mins: 80, goles: 1, asis: 1, xG: 0.78, nota: 8.8 },
      { nombre: 'Valverde',     pos: 'MCD', equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.21, nota: 7.6 },
      { nombre: 'Ter Stegen',   pos: 'POR', equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 6.3 },
      { nombre: 'Lewandowski',  pos: 'DC',  equipo: 'visitante', mins: 90, goles: 1, asis: 0, xG: 0.89, nota: 7.4 },
      { nombre: 'Pedri',        pos: 'MC',  equipo: 'visitante', mins: 90, goles: 0, asis: 1, xG: 0.18, nota: 7.0 },
      { nombre: 'Araujo',       pos: 'DFC', equipo: 'visitante', mins: 78, goles: 0, asis: 0, xG: 0.00, nota: 4.5 },
    ],
  },
  {
    id: 2,
    local:     { nombre: 'Atlético Madrid', abrev: 'ATM', color: '#ef4444' },
    visitante: { nombre: 'Sevilla FC',      abrev: 'SEV', color: '#f97316' },
    resultado: { local: 1, visitante: 0 },
    fecha: '19 Abr 2025', hora: '18:30', estado: 'jugado',
    estadio: 'Riyadh Air Metropolitano',
    xG: { local: 1.42, visitante: 0.71 },
    stats: {
      posesion:    { local: 55, visitante: 45 },
      tirosTotal:  { local: 11, visitante: 8  },
      tirosPuerta: { local: 5,  visitante: 3  },
      corners:     { local: 5,  visitante: 2  },
      faltas:      { local: 13, visitante: 16 },
      amarillas:   { local: 1,  visitante: 4  },
      rojas:       { local: 0,  visitante: 0  },
      fuerasJuego: { local: 2,  visitante: 4  },
    },
    timeline: [
      { min: 34, tipo: 'gol',         equipo: 'local',     jugador: 'Griezmann' },
      { min: 52, tipo: 'amarilla',    equipo: 'visitante', jugador: 'Navas' },
      { min: 61, tipo: 'amarilla',    equipo: 'local',     jugador: 'Giménez' },
      { min: 67, tipo: 'sustitucion', equipo: 'local',     jugador: 'Correa',   jugadorOut: 'Griezmann' },
      { min: 73, tipo: 'amarilla',    equipo: 'visitante', jugador: 'Badé' },
      { min: 81, tipo: 'sustitucion', equipo: 'visitante', jugador: 'Ocampos',  jugadorOut: 'Lukébakio' },
      { min: 88, tipo: 'amarilla',    equipo: 'visitante', jugador: 'Sow' },
    ],
    xgTimeline: [
      { min: 0,  local: 0,    visitante: 0    },
      { min: 20, local: 0.22, visitante: 0.11 },
      { min: 34, local: 0.81, visitante: 0.18 },
      { min: 45, local: 0.95, visitante: 0.35 },
      { min: 60, local: 1.10, visitante: 0.52 },
      { min: 75, local: 1.35, visitante: 0.65 },
      { min: 90, local: 1.42, visitante: 0.71 },
    ],
    disparos: [
      { x: 80, y: 31, tipo: 'gol',    equipo: 'local' },
      { x: 76, y: 27, tipo: 'parado', equipo: 'local' },
      { x: 73, y: 37, tipo: 'parado', equipo: 'local' },
      { x: 68, y: 22, tipo: 'fuera',  equipo: 'local' },
      { x: 71, y: 42, tipo: 'fuera',  equipo: 'local' },
      { x: 22, y: 32, tipo: 'parado', equipo: 'visitante' },
      { x: 28, y: 25, tipo: 'fuera',  equipo: 'visitante' },
      { x: 30, y: 40, tipo: 'fuera',  equipo: 'visitante' },
    ],
    jugadores: [
      { nombre: 'Oblak',     pos: 'POR', equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 7.8 },
      { nombre: 'Griezmann', pos: 'SS',  equipo: 'local',     mins: 67, goles: 1, asis: 0, xG: 0.58, nota: 8.5 },
      { nombre: 'De Paul',   pos: 'MC',  equipo: 'local',     mins: 90, goles: 0, asis: 1, xG: 0.22, nota: 7.8 },
      { nombre: 'Llorente',  pos: 'MD',  equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.11, nota: 7.2 },
      { nombre: 'Navas',     pos: 'POR', equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 7.1 },
      { nombre: 'Lukébakio', pos: 'EI',  equipo: 'visitante', mins: 81, goles: 0, asis: 0, xG: 0.31, nota: 7.1 },
      { nombre: 'Badé',      pos: 'DFC', equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 6.5 },
      { nombre: 'Sow',       pos: 'MC',  equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.18, nota: 6.8 },
    ],
  },
  {
    id: 3,
    local:     { nombre: 'Athletic Club', abrev: 'ATH', color: '#f87171' },
    visitante: { nombre: 'Valencia CF',   abrev: 'VLC', color: '#fbbf24' },
    resultado: { local: 2, visitante: 2 },
    fecha: '20 Abr 2025', hora: '16:15', estado: 'jugado',
    estadio: 'San Mamés',
    xG: { local: 1.93, visitante: 2.11 },
    stats: {
      posesion:    { local: 50, visitante: 50 },
      tirosTotal:  { local: 12, visitante: 11 },
      tirosPuerta: { local: 5,  visitante: 6  },
      corners:     { local: 7,  visitante: 4  },
      faltas:      { local: 14, visitante: 12 },
      amarillas:   { local: 3,  visitante: 2  },
      rojas:       { local: 0,  visitante: 0  },
      fuerasJuego: { local: 4,  visitante: 3  },
    },
    timeline: [
      { min: 18, tipo: 'gol',         equipo: 'local',     jugador: 'Williams I.' },
      { min: 35, tipo: 'gol',         equipo: 'visitante', jugador: 'Hugo Duro' },
      { min: 43, tipo: 'amarilla',    equipo: 'local',     jugador: 'Vivian' },
      { min: 54, tipo: 'gol',         equipo: 'local',     jugador: 'Guruzeta' },
      { min: 72, tipo: 'gol',         equipo: 'visitante', jugador: 'Hugo Duro' },
      { min: 78, tipo: 'sustitucion', equipo: 'local',     jugador: 'Berenguer',   jugadorOut: 'Williams I.' },
      { min: 83, tipo: 'amarilla',    equipo: 'visitante', jugador: 'J. Guerra' },
      { min: 87, tipo: 'sustitucion', equipo: 'visitante', jugador: 'Pepelu',      jugadorOut: 'Cenk Tosun' },
    ],
    xgTimeline: [
      { min: 0,  local: 0,    visitante: 0    },
      { min: 18, local: 0.64, visitante: 0.08 },
      { min: 30, local: 0.82, visitante: 0.41 },
      { min: 35, local: 0.88, visitante: 0.78 },
      { min: 45, local: 1.05, visitante: 0.95 },
      { min: 54, local: 1.51, visitante: 1.08 },
      { min: 72, local: 1.78, visitante: 1.89 },
      { min: 90, local: 1.93, visitante: 2.11 },
    ],
    disparos: [
      { x: 79, y: 29, tipo: 'gol',    equipo: 'local' },
      { x: 84, y: 35, tipo: 'gol',    equipo: 'local' },
      { x: 74, y: 25, tipo: 'parado', equipo: 'local' },
      { x: 70, y: 40, tipo: 'fuera',  equipo: 'local' },
      { x: 67, y: 22, tipo: 'fuera',  equipo: 'local' },
      { x: 20, y: 31, tipo: 'gol',    equipo: 'visitante' },
      { x: 17, y: 36, tipo: 'gol',    equipo: 'visitante' },
      { x: 24, y: 26, tipo: 'parado', equipo: 'visitante' },
      { x: 27, y: 41, tipo: 'parado', equipo: 'visitante' },
      { x: 32, y: 20, tipo: 'fuera',  equipo: 'visitante' },
    ],
    jugadores: [
      { nombre: 'Unai Simón',     pos: 'POR', equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 7.4 },
      { nombre: 'Williams I.',    pos: 'ED',  equipo: 'local',     mins: 78, goles: 1, asis: 1, xG: 0.72, nota: 8.3 },
      { nombre: 'Guruzeta',       pos: 'DC',  equipo: 'local',     mins: 90, goles: 1, asis: 0, xG: 0.58, nota: 7.6 },
      { nombre: 'Vivian',         pos: 'DFC', equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 6.8 },
      { nombre: 'Mamardashvili',  pos: 'POR', equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 7.2 },
      { nombre: 'Hugo Duro',      pos: 'DC',  equipo: 'visitante', mins: 90, goles: 2, asis: 0, xG: 1.24, nota: 8.1 },
      { nombre: 'Pepelu',         pos: 'MC',  equipo: 'visitante', mins: 90, goles: 0, asis: 1, xG: 0.18, nota: 7.3 },
      { nombre: 'Javi Guerra',    pos: 'MC',  equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.24, nota: 7.0 },
    ],
  },
  {
    id: 4,
    local:     { nombre: 'Real Betis',    abrev: 'BET', color: '#4ade80' },
    visitante: { nombre: 'Villarreal CF', abrev: 'VIL', color: '#eab308' },
    resultado: { local: 0, visitante: 2 },
    fecha: '20 Abr 2025', hora: '18:30', estado: 'jugado',
    estadio: 'Benito Villamarín',
    xG: { local: 0.82, visitante: 1.94 },
    stats: {
      posesion:    { local: 57, visitante: 43 },
      tirosTotal:  { local: 8,  visitante: 10 },
      tirosPuerta: { local: 2,  visitante: 5  },
      corners:     { local: 8,  visitante: 3  },
      faltas:      { local: 16, visitante: 11 },
      amarillas:   { local: 2,  visitante: 1  },
      rojas:       { local: 1,  visitante: 0  },
      fuerasJuego: { local: 2,  visitante: 5  },
    },
    timeline: [
      { min: 29, tipo: 'gol',         equipo: 'visitante', jugador: 'Danjuma' },
      { min: 48, tipo: 'roja',        equipo: 'local',     jugador: 'Bartra' },
      { min: 63, tipo: 'gol',         equipo: 'visitante', jugador: 'Baena' },
      { min: 71, tipo: 'amarilla',    equipo: 'local',     jugador: 'Isco' },
      { min: 79, tipo: 'sustitucion', equipo: 'visitante', jugador: 'Sorloth',    jugadorOut: 'Danjuma' },
      { min: 84, tipo: 'amarilla',    equipo: 'local',     jugador: 'Lo Celso' },
    ],
    xgTimeline: [
      { min: 0,  local: 0,    visitante: 0    },
      { min: 20, local: 0.18, visitante: 0.31 },
      { min: 29, local: 0.25, visitante: 0.88 },
      { min: 45, local: 0.48, visitante: 1.12 },
      { min: 63, local: 0.62, visitante: 1.71 },
      { min: 80, local: 0.78, visitante: 1.88 },
      { min: 90, local: 0.82, visitante: 1.94 },
    ],
    disparos: [
      { x: 72, y: 30, tipo: 'parado', equipo: 'local' },
      { x: 68, y: 38, tipo: 'parado', equipo: 'local' },
      { x: 65, y: 23, tipo: 'fuera',  equipo: 'local' },
      { x: 20, y: 31, tipo: 'gol',    equipo: 'visitante' },
      { x: 16, y: 35, tipo: 'gol',    equipo: 'visitante' },
      { x: 23, y: 26, tipo: 'parado', equipo: 'visitante' },
      { x: 27, y: 40, tipo: 'fuera',  equipo: 'visitante' },
    ],
    jugadores: [
      { nombre: 'Rui Silva',  pos: 'POR', equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 6.8 },
      { nombre: 'Isco',       pos: 'SS',  equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.21, nota: 6.8 },
      { nombre: 'Fekir',      pos: 'MC',  equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.31, nota: 7.1 },
      { nombre: 'Bartra',     pos: 'DFC', equipo: 'local',     mins: 48, goles: 0, asis: 0, xG: 0.00, nota: 4.9 },
      { nombre: 'Reina',      pos: 'POR', equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 7.5 },
      { nombre: 'Danjuma',    pos: 'EI',  equipo: 'visitante', mins: 79, goles: 1, asis: 1, xG: 0.81, nota: 8.6 },
      { nombre: 'Baena',      pos: 'MC',  equipo: 'visitante', mins: 90, goles: 1, asis: 0, xG: 0.62, nota: 8.0 },
      { nombre: 'Sorloth',    pos: 'DC',  equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.28, nota: 7.2 },
    ],
  },
  {
    id: 5,
    local:     { nombre: 'Getafe CF',      abrev: 'GET', color: '#60a5fa' },
    visitante: { nombre: 'Rayo Vallecano', abrev: 'RAY', color: '#fb923c' },
    resultado: { local: 1, visitante: 1 },
    fecha: '20 Abr 2025', hora: '21:00', estado: 'jugado',
    estadio: 'Coliseum Alfonso Pérez',
    xG: { local: 1.13, visitante: 1.31 },
    stats: {
      posesion:    { local: 44, visitante: 56 },
      tirosTotal:  { local: 9,  visitante: 10 },
      tirosPuerta: { local: 4,  visitante: 5  },
      corners:     { local: 3,  visitante: 5  },
      faltas:      { local: 18, visitante: 14 },
      amarillas:   { local: 5,  visitante: 3  },
      rojas:       { local: 0,  visitante: 0  },
      fuerasJuego: { local: 1,  visitante: 3  },
    },
    timeline: [
      { min: 37, tipo: 'gol',         equipo: 'local',     jugador: 'B. Mayoral' },
      { min: 51, tipo: 'amarilla',    equipo: 'local',     jugador: 'Arambarri' },
      { min: 58, tipo: 'gol',         equipo: 'visitante', jugador: 'Pathé Ciss' },
      { min: 65, tipo: 'amarilla',    equipo: 'local',     jugador: 'Catena' },
      { min: 69, tipo: 'sustitucion', equipo: 'visitante', jugador: 'Uche',        jugadorOut: 'Pathé Ciss' },
      { min: 74, tipo: 'amarilla',    equipo: 'local',     jugador: 'Óscar' },
      { min: 83, tipo: 'sustitucion', equipo: 'local',     jugador: 'Expósito',   jugadorOut: 'Djuric' },
      { min: 87, tipo: 'amarilla',    equipo: 'local',     jugador: 'Lejeune' },
    ],
    xgTimeline: [
      { min: 0,  local: 0,    visitante: 0    },
      { min: 25, local: 0.31, visitante: 0.22 },
      { min: 37, local: 0.78, visitante: 0.38 },
      { min: 45, local: 0.88, visitante: 0.51 },
      { min: 58, local: 0.98, visitante: 1.09 },
      { min: 75, local: 1.08, visitante: 1.24 },
      { min: 90, local: 1.13, visitante: 1.31 },
    ],
    disparos: [
      { x: 78, y: 32, tipo: 'gol',    equipo: 'local' },
      { x: 73, y: 27, tipo: 'parado', equipo: 'local' },
      { x: 70, y: 40, tipo: 'fuera',  equipo: 'local' },
      { x: 19, y: 32, tipo: 'gol',    equipo: 'visitante' },
      { x: 24, y: 27, tipo: 'parado', equipo: 'visitante' },
      { x: 28, y: 39, tipo: 'parado', equipo: 'visitante' },
      { x: 33, y: 22, tipo: 'fuera',  equipo: 'visitante' },
    ],
    jugadores: [
      { nombre: 'David Soria',  pos: 'POR', equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 7.3 },
      { nombre: 'B. Mayoral',   pos: 'DC',  equipo: 'local',     mins: 83, goles: 1, asis: 0, xG: 0.58, nota: 7.8 },
      { nombre: 'Arambarri',    pos: 'MCD', equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.18, nota: 6.9 },
      { nombre: 'Djené',        pos: 'DFC', equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 7.2 },
      { nombre: 'Dimitrievski', pos: 'POR', equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 7.4 },
      { nombre: 'Pathé Ciss',   pos: 'MCD', equipo: 'visitante', mins: 69, goles: 1, asis: 0, xG: 0.62, nota: 7.5 },
      { nombre: 'Nteka',        pos: 'EI',  equipo: 'visitante', mins: 90, goles: 0, asis: 1, xG: 0.21, nota: 7.1 },
      { nombre: 'Camello',      pos: 'DC',  equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.31, nota: 7.0 },
    ],
  },
  {
    id: 6,
    local:     { nombre: 'Real Sociedad', abrev: 'RSO', color: '#22d3ee' },
    visitante: { nombre: 'Girona FC',     abrev: 'GIR', color: '#f87171' },
    resultado: { local: 2, visitante: 0 },
    fecha: '21 Abr 2025', hora: '14:00', estado: 'jugado',
    estadio: 'Reale Arena',
    xG: { local: 2.31, visitante: 0.54 },
    stats: {
      posesion:    { local: 52, visitante: 48 },
      tirosTotal:  { local: 12, visitante: 7  },
      tirosPuerta: { local: 6,  visitante: 2  },
      corners:     { local: 6,  visitante: 2  },
      faltas:      { local: 10, visitante: 13 },
      amarillas:   { local: 1,  visitante: 3  },
      rojas:       { local: 0,  visitante: 0  },
      fuerasJuego: { local: 2,  visitante: 4  },
    },
    timeline: [
      { min: 31, tipo: 'gol',         equipo: 'local',     jugador: 'Oyarzabal' },
      { min: 46, tipo: 'amarilla',    equipo: 'visitante', jugador: 'M. Gutiérrez' },
      { min: 61, tipo: 'gol',         equipo: 'local',     jugador: 'Oyarzabal' },
      { min: 71, tipo: 'amarilla',    equipo: 'visitante', jugador: 'Aramburu' },
      { min: 78, tipo: 'sustitucion', equipo: 'local',     jugador: 'Sadiq',      jugadorOut: 'Kubo' },
      { min: 83, tipo: 'sustitucion', equipo: 'visitante', jugador: 'El-Ouazzani',jugadorOut: 'Dovbyk' },
      { min: 88, tipo: 'amarilla',    equipo: 'visitante', jugador: 'Blind' },
    ],
    xgTimeline: [
      { min: 0,  local: 0,    visitante: 0    },
      { min: 20, local: 0.38, visitante: 0.09 },
      { min: 31, local: 0.97, visitante: 0.14 },
      { min: 45, local: 1.11, visitante: 0.28 },
      { min: 61, local: 1.78, visitante: 0.41 },
      { min: 75, local: 2.15, visitante: 0.49 },
      { min: 90, local: 2.31, visitante: 0.54 },
    ],
    disparos: [
      { x: 81, y: 30, tipo: 'gol',    equipo: 'local' },
      { x: 76, y: 36, tipo: 'gol',    equipo: 'local' },
      { x: 74, y: 26, tipo: 'parado', equipo: 'local' },
      { x: 69, y: 38, tipo: 'parado', equipo: 'local' },
      { x: 72, y: 43, tipo: 'fuera',  equipo: 'local' },
      { x: 25, y: 32, tipo: 'parado', equipo: 'visitante' },
      { x: 29, y: 40, tipo: 'fuera',  equipo: 'visitante' },
    ],
    jugadores: [
      { nombre: 'Remiro',       pos: 'POR', equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 7.9 },
      { nombre: 'Oyarzabal',    pos: 'DC',  equipo: 'local',     mins: 90, goles: 2, asis: 0, xG: 1.24, nota: 9.0 },
      { nombre: 'Merino',       pos: 'MC',  equipo: 'local',     mins: 90, goles: 0, asis: 1, xG: 0.28, nota: 8.2 },
      { nombre: 'Kubo',         pos: 'ED',  equipo: 'local',     mins: 78, goles: 0, asis: 1, xG: 0.41, nota: 7.8 },
      { nombre: 'Gazzaniga',    pos: 'POR', equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 6.5 },
      { nombre: 'Sávio',        pos: 'ED',  equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.21, nota: 6.9 },
      { nombre: 'Dovbyk',       pos: 'DC',  equipo: 'visitante', mins: 83, goles: 0, asis: 0, xG: 0.18, nota: 6.4 },
      { nombre: 'M. Gutiérrez', pos: 'LD',  equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 6.3 },
    ],
  },
  {
    id: 7,
    local:     { nombre: 'Celta Vigo', abrev: 'CEL', color: '#7dd3fc' },
    visitante: { nombre: 'CA Osasuna', abrev: 'OSA', color: '#dc2626' },
    resultado: { local: 0, visitante: 3 },
    fecha: '21 Abr 2025', hora: '16:15', estado: 'jugado',
    estadio: 'Abanca Balaídos',
    xG: { local: 0.61, visitante: 2.73 },
    stats: {
      posesion:    { local: 46, visitante: 54 },
      tirosTotal:  { local: 8,  visitante: 13 },
      tirosPuerta: { local: 1,  visitante: 7  },
      corners:     { local: 4,  visitante: 7  },
      faltas:      { local: 16, visitante: 11 },
      amarillas:   { local: 3,  visitante: 2  },
      rojas:       { local: 1,  visitante: 0  },
      fuerasJuego: { local: 5,  visitante: 1  },
    },
    timeline: [
      { min: 12, tipo: 'gol',         equipo: 'visitante', jugador: 'Budimir' },
      { min: 28, tipo: 'amarilla',    equipo: 'local',     jugador: 'Mingueza' },
      { min: 41, tipo: 'gol',         equipo: 'visitante', jugador: 'Moncayola' },
      { min: 51, tipo: 'roja',        equipo: 'local',     jugador: 'Aidoo' },
      { min: 68, tipo: 'gol',         equipo: 'visitante', jugador: 'Budimir' },
      { min: 72, tipo: 'sustitucion', equipo: 'visitante', jugador: 'Chimy Ávila', jugadorOut: 'Moncayola' },
      { min: 78, tipo: 'amarilla',    equipo: 'local',     jugador: 'Kevin' },
      { min: 84, tipo: 'sustitucion', equipo: 'local',     jugador: 'Cervi',       jugadorOut: 'Aspas' },
    ],
    xgTimeline: [
      { min: 0,  local: 0,    visitante: 0    },
      { min: 12, local: 0.09, visitante: 0.71 },
      { min: 30, local: 0.22, visitante: 1.08 },
      { min: 41, local: 0.31, visitante: 1.52 },
      { min: 45, local: 0.38, visitante: 1.65 },
      { min: 68, local: 0.55, visitante: 2.61 },
      { min: 90, local: 0.61, visitante: 2.73 },
    ],
    disparos: [
      { x: 71, y: 30, tipo: 'parado', equipo: 'local' },
      { x: 68, y: 38, tipo: 'fuera',  equipo: 'local' },
      { x: 65, y: 23, tipo: 'fuera',  equipo: 'local' },
      { x: 18, y: 31, tipo: 'gol',    equipo: 'visitante' },
      { x: 15, y: 35, tipo: 'gol',    equipo: 'visitante' },
      { x: 21, y: 27, tipo: 'gol',    equipo: 'visitante' },
      { x: 26, y: 38, tipo: 'parado', equipo: 'visitante' },
      { x: 30, y: 24, tipo: 'parado', equipo: 'visitante' },
      { x: 35, y: 42, tipo: 'fuera',  equipo: 'visitante' },
    ],
    jugadores: [
      { nombre: 'Guaita',       pos: 'POR', equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 6.1 },
      { nombre: 'Aspas',        pos: 'DC',  equipo: 'local',     mins: 84, goles: 0, asis: 0, xG: 0.28, nota: 6.5 },
      { nombre: 'Mingueza',     pos: 'LD',  equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 6.4 },
      { nombre: 'Kevin',        pos: 'MC',  equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.18, nota: 6.2 },
      { nombre: 'S. Herrera',   pos: 'POR', equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 8.2 },
      { nombre: 'Budimir',      pos: 'DC',  equipo: 'visitante', mins: 90, goles: 2, asis: 0, xG: 1.48, nota: 9.1 },
      { nombre: 'Moncayola',    pos: 'MC',  equipo: 'visitante', mins: 72, goles: 1, asis: 1, xG: 0.62, nota: 8.3 },
      { nombre: 'Chimy Ávila',  pos: 'ED',  equipo: 'visitante', mins: 90, goles: 0, asis: 1, xG: 0.31, nota: 7.8 },
    ],
  },
  {
    id: 8,
    local:     { nombre: 'Espanyol',     abrev: 'ESP', color: '#60a5fa' },
    visitante: { nombre: 'RCD Mallorca', abrev: 'MAL', color: '#ef4444' },
    resultado: { local: 1, visitante: 2 },
    fecha: '21 Abr 2025', hora: '21:00', estado: 'jugado',
    estadio: 'RCDE Stadium',
    xG: { local: 1.18, visitante: 1.82 },
    stats: {
      posesion:    { local: 53, visitante: 47 },
      tirosTotal:  { local: 10, visitante: 12 },
      tirosPuerta: { local: 4,  visitante: 6  },
      corners:     { local: 5,  visitante: 4  },
      faltas:      { local: 12, visitante: 13 },
      amarillas:   { local: 2,  visitante: 2  },
      rojas:       { local: 0,  visitante: 0  },
      fuerasJuego: { local: 2,  visitante: 3  },
    },
    timeline: [
      { min: 22, tipo: 'gol',         equipo: 'visitante', jugador: 'Muriqi' },
      { min: 45, tipo: 'gol',         equipo: 'local',     jugador: 'Puado' },
      { min: 49, tipo: 'gol',         equipo: 'visitante', jugador: 'D. Rodríguez' },
      { min: 58, tipo: 'amarilla',    equipo: 'local',     jugador: 'Cabrera' },
      { min: 67, tipo: 'sustitucion', equipo: 'local',     jugador: 'Lee',          jugadorOut: 'Brian' },
      { min: 73, tipo: 'amarilla',    equipo: 'visitante', jugador: 'Russo' },
      { min: 79, tipo: 'sustitucion', equipo: 'visitante', jugador: 'Abdon',        jugadorOut: 'Muriqi' },
      { min: 85, tipo: 'amarilla',    equipo: 'local',     jugador: 'Vidal' },
    ],
    xgTimeline: [
      { min: 0,  local: 0,    visitante: 0    },
      { min: 22, local: 0.18, visitante: 0.78 },
      { min: 35, local: 0.41, visitante: 0.98 },
      { min: 45, local: 0.88, visitante: 1.04 },
      { min: 49, local: 0.91, visitante: 1.64 },
      { min: 65, local: 1.05, visitante: 1.74 },
      { min: 90, local: 1.18, visitante: 1.82 },
    ],
    disparos: [
      { x: 79, y: 31, tipo: 'gol',    equipo: 'local' },
      { x: 74, y: 26, tipo: 'parado', equipo: 'local' },
      { x: 71, y: 37, tipo: 'parado', equipo: 'local' },
      { x: 68, y: 22, tipo: 'fuera',  equipo: 'local' },
      { x: 19, y: 31, tipo: 'gol',    equipo: 'visitante' },
      { x: 16, y: 36, tipo: 'gol',    equipo: 'visitante' },
      { x: 23, y: 26, tipo: 'parado', equipo: 'visitante' },
      { x: 27, y: 40, tipo: 'fuera',  equipo: 'visitante' },
      { x: 31, y: 22, tipo: 'fuera',  equipo: 'visitante' },
    ],
    jugadores: [
      { nombre: 'Joan García',   pos: 'POR', equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 6.8 },
      { nombre: 'Puado',         pos: 'ED',  equipo: 'local',     mins: 90, goles: 1, asis: 0, xG: 0.58, nota: 7.3 },
      { nombre: 'Vidal',         pos: 'MCD', equipo: 'local',     mins: 90, goles: 0, asis: 0, xG: 0.18, nota: 6.4 },
      { nombre: 'Brian Oliván',  pos: 'LD',  equipo: 'local',     mins: 67, goles: 0, asis: 0, xG: 0.09, nota: 6.5 },
      { nombre: 'Rajković',      pos: 'POR', equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.00, nota: 7.6 },
      { nombre: 'Muriqi',        pos: 'DC',  equipo: 'visitante', mins: 79, goles: 1, asis: 1, xG: 0.89, nota: 8.7 },
      { nombre: 'D. Rodríguez',  pos: 'MC',  equipo: 'visitante', mins: 90, goles: 1, asis: 0, xG: 0.52, nota: 7.9 },
      { nombre: 'Abdon Prats',   pos: 'DC',  equipo: 'visitante', mins: 90, goles: 0, asis: 0, xG: 0.21, nota: 7.2 },
    ],
  },
]

/* ══════════════════════════════════════════════════════
   DATA — Partidos en directo (simulados)
══════════════════════════════════════════════════════ */
const DIRECTO = [
  {
    id: 'd1',
    minuto: 23,
    estado: 'Primera parte',
    local:     { nombre: 'Real Madrid',   abrev: 'RMA', color: '#e2e8f0', goles: 1, xG: 1.4 },
    visitante: { nombre: 'Athletic Club', abrev: 'ATH', color: '#fb7185', goles: 0, xG: 0.6 },
    estadisticas: { posesion: [58, 42], tiros: [5, 2], corners: [3, 1], faltas: [4, 6] },
    eventos: [
      { minuto: 1,  tipo: 'inicio',          texto: 'Inicio del partido',  equipo: null },
      { minuto: 12, tipo: 'tarjeta_amarilla', texto: 'Berenguer',           equipo: 'visitante' },
      { minuto: 18, tipo: 'gol',              texto: 'Vinícius Jr.',        equipo: 'local',     marcador: '1-0' },
    ],
    xg_timeline: [
      { m: 0,  L: 0,   V: 0   },
      { m: 5,  L: 0.2, V: 0   },
      { m: 10, L: 0.2, V: 0.3 },
      { m: 15, L: 0.6, V: 0.3 },
      { m: 18, L: 1.1, V: 0.4 },
      { m: 20, L: 1.2, V: 0.5 },
      { m: 23, L: 1.4, V: 0.6 },
    ],
  },
  {
    id: 'd2',
    minuto: 67,
    estado: 'Segunda parte',
    local:     { nombre: 'FC Barcelona',  abrev: 'FCB', color: '#60a5fa', goles: 2, xG: 2.8 },
    visitante: { nombre: 'Villarreal CF', abrev: 'VIL', color: '#fbbf24', goles: 1, xG: 1.9 },
    estadisticas: { posesion: [62, 38], tiros: [11, 7], corners: [6, 3], faltas: [9, 11] },
    eventos: [
      { minuto: 1,  tipo: 'inicio',          texto: 'Inicio del partido',       equipo: null },
      { minuto: 14, tipo: 'gol',              texto: 'Lewandowski',              equipo: 'local',     marcador: '1-0' },
      { minuto: 31, tipo: 'tarjeta_amarilla', texto: 'Parejo',                   equipo: 'visitante' },
      { minuto: 38, tipo: 'gol',              texto: 'Álex Baena',               equipo: 'visitante', marcador: '1-1' },
      { minuto: 45, tipo: 'descanso',         texto: 'Descanso',                 equipo: null },
      { minuto: 53, tipo: 'sustitucion',      texto: 'Sale: Gavi — Entra: Pedri',equipo: 'local' },
      { minuto: 61, tipo: 'gol',              texto: 'Pedri',                    equipo: 'local',     marcador: '2-1' },
      { minuto: 67, tipo: 'tarjeta_amarilla', texto: 'Albiol',                   equipo: 'visitante' },
    ],
    xg_timeline: [
      { m: 0,  L: 0,   V: 0   },
      { m: 5,  L: 0.3, V: 0.1 },
      { m: 10, L: 0.5, V: 0.3 },
      { m: 14, L: 1.1, V: 0.3 },
      { m: 20, L: 1.3, V: 0.6 },
      { m: 30, L: 1.6, V: 1.0 },
      { m: 38, L: 1.7, V: 1.5 },
      { m: 45, L: 1.9, V: 1.7 },
      { m: 55, L: 2.2, V: 1.8 },
      { m: 61, L: 2.6, V: 1.8 },
      { m: 67, L: 2.8, V: 1.9 },
    ],
  },
  {
    id: 'd3',
    minuto: 88,
    estado: 'Segunda parte',
    local:     { nombre: 'Atl. de Madrid', abrev: 'ATM', color: '#f87171', goles: 1, xG: 1.6 },
    visitante: { nombre: 'Real Sociedad',  abrev: 'RSO', color: '#818cf8', goles: 1, xG: 1.8 },
    estadisticas: { posesion: [44, 56], tiros: [8, 10], corners: [4, 7], faltas: [13, 8] },
    eventos: [
      { minuto: 1,  tipo: 'inicio',          texto: 'Inicio del partido',            equipo: null },
      { minuto: 22, tipo: 'tarjeta_amarilla', texto: 'Llorente',                      equipo: 'local' },
      { minuto: 35, tipo: 'gol',              texto: 'Kubo',                          equipo: 'visitante', marcador: '0-1' },
      { minuto: 41, tipo: 'tarjeta_amarilla', texto: 'Zubimendi',                     equipo: 'visitante' },
      { minuto: 45, tipo: 'descanso',         texto: 'Descanso',                      equipo: null },
      { minuto: 51, tipo: 'sustitucion',      texto: 'Sale: Correa — Entra: Sørloth', equipo: 'local' },
      { minuto: 58, tipo: 'tarjeta_amarilla', texto: 'Merino',                        equipo: 'visitante' },
      { minuto: 63, tipo: 'sustitucion',      texto: 'Sale: Oyarzabal — Entra: Mendez',equipo: 'visitante' },
      { minuto: 71, tipo: 'gol',              texto: 'Griezmann',                     equipo: 'local',     marcador: '1-1' },
      { minuto: 79, tipo: 'tarjeta_roja',     texto: 'Tierney',                       equipo: 'visitante' },
      { minuto: 84, tipo: 'sustitucion',      texto: 'Sale: Griezmann — Entra: Morata',equipo: 'local' },
      { minuto: 88, tipo: 'tarjeta_amarilla', texto: 'Savić',                         equipo: 'local' },
    ],
    xg_timeline: [
      { m: 0,  L: 0,   V: 0   },
      { m: 5,  L: 0.1, V: 0.2 },
      { m: 15, L: 0.3, V: 0.6 },
      { m: 25, L: 0.4, V: 0.7 },
      { m: 35, L: 0.6, V: 1.4 },
      { m: 45, L: 0.8, V: 1.5 },
      { m: 55, L: 1.0, V: 1.6 },
      { m: 65, L: 1.1, V: 1.8 },
      { m: 71, L: 1.5, V: 1.8 },
      { m: 80, L: 1.6, V: 1.8 },
      { m: 88, L: 1.6, V: 1.8 },
    ],
  },
]

/* ══════════════════════════════════════════════════════
   LIVE — helpers & components
══════════════════════════════════════════════════════ */
const LIVE_ICON = {
  gol:              '⚽',
  tarjeta_amarilla: '🟨',
  tarjeta_roja:     '🟥',
  sustitucion:      '🔄',
  inicio:           '▶',
  descanso:         '⏸',
}

function LiveDot() {
  return (
    <span className="relative flex h-2.5 w-2.5 shrink-0">
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60" />
      <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-400" />
    </span>
  )
}

function LiveCard({ partido, selected, onClick }) {
  const ultimo = partido.eventos.at(-1)
  const C_L = '#22d3ee'
  const C_V = '#f87171'
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-2xl border transition-all duration-200 will-change-transform
        hover:scale-[1.01] ${
          selected
            ? 'bg-slate-800/80 border-cyan-500/50 shadow-md shadow-cyan-950/40'
            : 'bg-slate-900 border-slate-800 hover:border-slate-700'
        }`}
    >
      <div className="p-4">
        {/* Estado + minuto */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <LiveDot />
            <span className="text-xs font-bold text-emerald-400 tracking-wider">EN DIRECTO</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-black text-white tabular-nums">{partido.minuto}'</span>
            <span className="text-xs text-slate-500">· {partido.estado}</span>
          </div>
        </div>

        {/* Marcador */}
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 mb-4">
          <div className="flex flex-col items-center gap-1.5">
            <div className="w-11 h-11 rounded-xl flex items-center justify-center text-xs font-black"
                 style={{ background: `${partido.local.color}18`, color: partido.local.color, border: `1.5px solid ${partido.local.color}40` }}>
              {partido.local.abrev}
            </div>
            <p className="text-xs font-semibold text-white text-center leading-tight">{partido.local.nombre}</p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-3xl font-black text-white tabular-nums">{partido.local.goles}</span>
            <span className="text-slate-600 font-black">–</span>
            <span className="text-3xl font-black text-white tabular-nums">{partido.visitante.goles}</span>
          </div>

          <div className="flex flex-col items-center gap-1.5">
            <div className="w-11 h-11 rounded-xl flex items-center justify-center text-xs font-black"
                 style={{ background: `${partido.visitante.color}18`, color: partido.visitante.color, border: `1.5px solid ${partido.visitante.color}40` }}>
              {partido.visitante.abrev}
            </div>
            <p className="text-xs font-semibold text-white text-center leading-tight">{partido.visitante.nombre}</p>
          </div>
        </div>

        {/* xG */}
        <div className="flex items-center justify-between text-xs mb-3">
          <span style={{ color: C_L }} className="font-bold tabular-nums">xG {partido.local.xG}</span>
          <div className="flex-1 mx-3 h-1 bg-slate-800 rounded-full overflow-hidden flex">
            <div className="rounded-l-full" style={{ width: `${(partido.local.xG / (partido.local.xG + partido.visitante.xG)) * 100}%`, backgroundColor: C_L }} />
            <div className="rounded-r-full flex-1" style={{ backgroundColor: C_V }} />
          </div>
          <span style={{ color: C_V }} className="font-bold tabular-nums">xG {partido.visitante.xG}</span>
        </div>

        {/* Último evento */}
        {ultimo && (
          <div className="flex items-center gap-2 rounded-xl px-3 py-2 bg-slate-800/60 border border-slate-700/40">
            <span className="text-sm shrink-0">{LIVE_ICON[ultimo.tipo] ?? '•'}</span>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-white truncate">{ultimo.texto}</p>
              {ultimo.marcador && <p className="text-[10px] text-cyan-400 font-bold">→ {ultimo.marcador}</p>}
            </div>
            <span className="text-[10px] font-bold text-slate-500 shrink-0 tabular-nums">{ultimo.minuto}'</span>
          </div>
        )}
      </div>
    </button>
  )
}

function XgTooltipLive({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-slate-400 mb-1.5">Min. {label}'</p>
      {payload.map(p => (
        <div key={p.name} className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: p.color }} />
          <span className="text-slate-300">{p.name}</span>
          <span className="font-black text-white ml-auto pl-3 tabular-nums">{p.value}</span>
        </div>
      ))}
    </div>
  )
}

function LiveStatBar({ label, local, visitante }) {
  const total = (local + visitante) || 1
  const pctL  = Math.round((local / total) * 100)
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="font-black text-white tabular-nums">{local}</span>
        <span className="text-slate-500 text-[11px]">{label}</span>
        <span className="font-black text-white tabular-nums">{visitante}</span>
      </div>
      <div className="flex h-1.5 rounded-full overflow-hidden">
        <div className="rounded-l-full" style={{ width: `${pctL}%`, backgroundColor: '#22d3ee' }} />
        <div className="rounded-r-full flex-1" style={{ backgroundColor: '#f87171' }} />
      </div>
    </div>
  )
}

function LiveDetailPanel({ partido }) {
  const C_L = '#22d3ee'
  const C_V = '#f87171'
  return (
    <div className="flex flex-col gap-5 animate-fade-in">

      {/* xG acumulado minuto a minuto */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
        <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">xG acumulado</p>
        <div className="flex gap-5 mb-3">
          <span className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: C_L }}>
            <span className="w-3 h-1 rounded-full inline-block" style={{ backgroundColor: C_L }} />
            {partido.local.nombre}
          </span>
          <span className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: C_V }}>
            <span className="w-3 h-1 rounded-full inline-block" style={{ backgroundColor: C_V }} />
            {partido.visitante.nombre}
          </span>
        </div>
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={partido.xg_timeline} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              <XAxis dataKey="m" tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={v => `${v}'`} />
              <YAxis tick={{ fill: '#64748b', fontSize: 10 }} tickLine={false} axisLine={false} domain={[0, 'auto']} />
              <Tooltip content={<XgTooltipLive />} cursor={{ stroke: '#334155', strokeWidth: 1 }} />
              <Line type="monotone" dataKey="L" name={partido.local.abrev} stroke={C_L} strokeWidth={2}
                dot={false} activeDot={{ r: 4, fill: C_L, stroke: '#020617', strokeWidth: 2 }}
                isAnimationActive animationDuration={700} animationEasing="ease-out" />
              <Line type="monotone" dataKey="V" name={partido.visitante.abrev} stroke={C_V} strokeWidth={2}
                dot={false} activeDot={{ r: 4, fill: C_V, stroke: '#020617', strokeWidth: 2 }}
                isAnimationActive animationDuration={700} animationEasing="ease-out" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Estadísticas en vivo */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-4">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">Estadísticas</p>
          <div className="flex gap-3 text-[11px] font-semibold">
            <span style={{ color: C_L }}>{partido.local.abrev}</span>
            <span style={{ color: C_V }}>{partido.visitante.abrev}</span>
          </div>
        </div>
        <div className="space-y-3">
          <LiveStatBar label="Posesión %" local={partido.estadisticas.posesion[0]} visitante={partido.estadisticas.posesion[1]} />
          <LiveStatBar label="Tiros"      local={partido.estadisticas.tiros[0]}    visitante={partido.estadisticas.tiros[1]} />
          <LiveStatBar label="Córners"    local={partido.estadisticas.corners[0]}  visitante={partido.estadisticas.corners[1]} />
          <LiveStatBar label="Faltas"     local={partido.estadisticas.faltas[0]}   visitante={partido.estadisticas.faltas[1]} />
        </div>
      </div>

      {/* Timeline de eventos */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-widest">Timeline</p>
          <div className="flex items-center gap-1.5">
            <LiveDot />
            <span className="text-xs font-bold text-emerald-400">Min. {partido.minuto}'</span>
          </div>
        </div>
        <div className="divide-y divide-slate-800/50">
          {[...partido.eventos].reverse().map((ev, i) => {
            const col = ev.equipo === 'local'     ? partido.local.color
                      : ev.equipo === 'visitante' ? partido.visitante.color
                      : '#64748b'
            return (
              <div key={i} className={`flex items-center gap-3 px-5 py-3 ${i === 0 ? 'bg-cyan-400/5' : ''}`}>
                <span className={`text-xs font-black tabular-nums w-8 shrink-0 ${i === 0 ? 'text-cyan-400' : 'text-slate-500'}`}>
                  {ev.minuto}'
                </span>
                <span className="text-base shrink-0 w-6 text-center">{LIVE_ICON[ev.tipo] ?? '•'}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-white truncate">{ev.texto}</p>
                  {ev.marcador && <p className="text-[11px] font-bold text-cyan-400">{ev.marcador}</p>}
                </div>
                {ev.equipo && <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: col }} />}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

/* ══════════════════════════════════════════════════════
   MATCH TIMELINE
══════════════════════════════════════════════════════ */
function EventIcon({ tipo, cx, cy }) {
  if (tipo === 'gol') {
    return (
      <g>
        <circle cx={cx} cy={cy} r={7.5} fill="#22d3ee" fillOpacity={0.12} />
        <circle cx={cx} cy={cy} r={5} fill="#22d3ee" />
        <text x={cx} y={cy + 1.8} textAnchor="middle" fontSize={5.5} fontWeight="bold" fill="#0c1a2e">G</text>
      </g>
    )
  }
  if (tipo === 'amarilla') {
    return <rect x={cx - 3.5} y={cy - 5} width={7} height={10} rx={1.2} fill="#fbbf24" />
  }
  if (tipo === 'roja') {
    return <rect x={cx - 3.5} y={cy - 5} width={7} height={10} rx={1.2} fill="#ef4444" />
  }
  if (tipo === 'sustitucion') {
    return (
      <g>
        <circle cx={cx} cy={cy} r={5.5} fill="#1e293b" stroke="#475569" strokeWidth={0.8} />
        <path d={`M${cx},${cy - 4} L${cx + 3},${cy - 1} L${cx - 3},${cy - 1} Z`} fill="#4ade80" />
        <path d={`M${cx},${cy + 4} L${cx + 3},${cy + 1} L${cx - 3},${cy + 1} Z`} fill="#f87171" />
      </g>
    )
  }
  return null
}

function MatchTimeline({ events }) {
  const W = 400, H = 98
  const xMin = 16, xMax = 384
  const barY = 46
  const localIconY = 19
  const visitIconY  = 73

  function xPos(min) {
    return xMin + (Math.min(min, 90) / 90) * (xMax - xMin)
  }

  const localEv    = events.filter(e => e.equipo === 'local')
  const visitanteEv = events.filter(e => e.equipo === 'visitante')
  const ticks = [0, 15, 30, 45, 60, 75, 90]

  return (
    <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Línea de tiempo</h4>
        <div className="flex items-center gap-3 text-[10px] text-slate-500">
          <span className="flex items-center gap-1">
            <span className="w-2 h-3 rounded-sm bg-yellow-400 inline-block" /> Amarilla
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-3 rounded-sm bg-red-500 inline-block" /> Roja
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-full bg-cyan-400 inline-block" /> Gol
          </span>
          <span className="flex items-center gap-1">
            <span className="w-3 h-3 rounded-full bg-slate-600 inline-block border border-slate-500" /> Cambio
          </span>
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        {/* Team side labels */}
        <text x={xMin} y={barY - 10} fontSize={5} fill="#22d3ee" fontWeight="600">LOCAL</text>
        <text x={xMin} y={barY + 15} fontSize={5} fill="#a78bfa" fontWeight="600">VISITANTE</text>

        {/* Center bar */}
        <line x1={xMin} y1={barY} x2={xMax} y2={barY} stroke="#334155" strokeWidth={1.5} strokeLinecap="round" />

        {/* Tick marks */}
        {ticks.map(t => (
          <line key={t}
            x1={xPos(t)} y1={barY - 3}
            x2={xPos(t)} y2={barY + 3}
            stroke="#1e3a4a" strokeWidth={0.8}
          />
        ))}

        {/* Halftime dashed marker */}
        <line
          x1={xPos(45)} y1={barY - 18}
          x2={xPos(45)} y2={barY + 18}
          stroke="#334155" strokeDasharray="2.5 2" strokeWidth={0.8}
        />
        <text x={xPos(45)} y={barY + 26} textAnchor="middle" fontSize={4.5} fill="#475569">HT</text>

        {/* Minute axis labels */}
        {[0, 45, 90].map(t => (
          <text key={t} x={xPos(t)} y={H - 1} textAnchor="middle" fontSize={4.5} fill="#334155">{t}'</text>
        ))}

        {/* Local events (above bar) */}
        {localEv.map((ev, i) => {
          const x = xPos(ev.min)
          return (
            <g key={`l${i}`}>
              <line x1={x} y1={barY - 1} x2={x} y2={localIconY + 6} stroke="#334155" strokeWidth={0.6} />
              <EventIcon tipo={ev.tipo} cx={x} cy={localIconY} />
              <text x={x} y={7} textAnchor="middle" fontSize={4.5} fill="#64748b">{ev.min}'</text>
            </g>
          )
        })}

        {/* Visitante events (below bar) */}
        {visitanteEv.map((ev, i) => {
          const x = xPos(ev.min)
          return (
            <g key={`v${i}`}>
              <line x1={x} y1={barY + 1} x2={x} y2={visitIconY - 6} stroke="#334155" strokeWidth={0.6} />
              <EventIcon tipo={ev.tipo} cx={x} cy={visitIconY} />
              <text x={x} y={H - 12} textAnchor="middle" fontSize={4.5} fill="#64748b">{ev.min}'</text>
            </g>
          )
        })}
      </svg>

      {/* Event list — compact text log */}
      <div className="mt-3 flex flex-col gap-1 max-h-36 overflow-y-auto">
        {[...events].sort((a, b) => a.min - b.min).map((ev, i) => {
          const isLocal = ev.equipo === 'local'
          const evLabel = {
            gol: '⚽ Gol',
            amarilla: '🟨 Amarilla',
            roja: '🟥 Roja',
            sustitucion: '🔄 Cambio',
          }[ev.tipo]
          return (
            <div key={i} className={`flex items-center gap-2 text-[11px] ${isLocal ? 'flex-row' : 'flex-row-reverse'}`}>
              <span className="text-slate-600 tabular-nums w-7 shrink-0 text-right">{ev.min}'</span>
              <span className={`font-medium ${isLocal ? 'text-cyan-400' : 'text-violet-400'}`}>{evLabel}</span>
              <span className="text-slate-300 truncate">{ev.jugador}</span>
              {ev.jugadorOut && (
                <span className="text-slate-600 truncate hidden sm:block">← {ev.jugadorOut}</span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ══════════════════════════════════════════════════════
   XG ACUMULADO CHART
══════════════════════════════════════════════════════ */
function XGTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-slate-400 mb-1">min. {label}'</p>
      {payload.map(p => (
        <p key={p.dataKey} style={{ color: p.color }} className="font-bold">
          {p.dataKey === 'local' ? 'Local' : 'Visitante'}: {Number(p.value).toFixed(2)} xG
        </p>
      ))}
    </div>
  )
}

function XGChart({ xgTimeline, localNombre, visitanteNombre }) {
  return (
    <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">xG acumulado</h4>
        <div className="flex items-center gap-4 text-[11px]">
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-5 h-0.5 bg-cyan-400 rounded" />
            <span className="text-slate-400 truncate max-w-[80px]">{localNombre}</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-5 h-0.5 bg-violet-400 rounded" />
            <span className="text-slate-400 truncate max-w-[80px]">{visitanteNombre}</span>
          </span>
        </div>
      </div>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={xgTimeline} margin={{ top: 4, right: 4, left: -22, bottom: 0 }}>
            <XAxis
              dataKey="min"
              tick={{ fill: '#64748b', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={v => `${v}'`}
            />
            <YAxis
              tick={{ fill: '#64748b', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickCount={4}
            />
            <Tooltip content={<XGTooltip />} cursor={{ stroke: '#334155', strokeWidth: 1 }} />
            <ReferenceLine x={45} stroke="#1e293b" strokeDasharray="4 3" label="" />
            <Line
              type="monotone" dataKey="local" stroke="#22d3ee" strokeWidth={2.5}
              dot={false} activeDot={{ r: 4, fill: '#22d3ee', stroke: '#0c1a2e', strokeWidth: 2 }}
              isAnimationActive animationDuration={700} animationEasing="ease-out"
            />
            <Line
              type="monotone" dataKey="visitante" stroke="#a78bfa" strokeWidth={2.5}
              dot={false} activeDot={{ r: 4, fill: '#a78bfa', stroke: '#0c1a2e', strokeWidth: 2 }}
              isAnimationActive animationDuration={700} animationEasing="ease-out"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

/* ══════════════════════════════════════════════════════
   STAT ROW
══════════════════════════════════════════════════════ */
function StatRow({ label, local, visitante, suffix = '', invert = false }) {
  const total = (local + visitante) || 1
  const localWins    = invert ? local <= visitante : local >= visitante
  const visitanteWins = invert ? visitante <= local : visitante >= local
  const localPct = (local / total) * 100

  return (
    <div className="grid items-center gap-2" style={{ gridTemplateColumns: '3rem 1fr 3rem' }}>
      <span className={`text-right text-sm font-bold tabular-nums ${localWins && local !== visitante ? 'text-cyan-400' : 'text-slate-300'}`}>
        {local}{suffix}
      </span>
      <div className="relative h-2 bg-slate-800 rounded-full overflow-hidden">
        <div
          className={`absolute left-0 top-0 h-full rounded-l-full transition-all duration-700 ${localWins && local !== visitante ? 'bg-cyan-400' : 'bg-slate-600'}`}
          style={{ width: `${localPct}%` }}
        />
        <div
          className={`absolute right-0 top-0 h-full rounded-r-full transition-all duration-700 ${visitanteWins && local !== visitante ? 'bg-violet-400' : 'bg-slate-700'}`}
          style={{ width: `${100 - localPct}%` }}
        />
      </div>
      <span className={`text-left text-sm font-bold tabular-nums ${visitanteWins && local !== visitante ? 'text-violet-400' : 'text-slate-300'}`}>
        {visitante}{suffix}
      </span>
    </div>
  )
}

/* ══════════════════════════════════════════════════════
   SHOT MAP (mejorado)
══════════════════════════════════════════════════════ */
function ShotMap({ disparos }) {
  const lp = {
    border: { x: 1, y: 1, w: 98, h: 63 },
    lpa: { x: 1, y: 15.5, w: 17, h: 34 },
    rpa: { x: 82, y: 15.5, w: 17, h: 34 },
    lga: { x: 1, y: 24, w: 6.5, h: 17 },
    rga: { x: 92.5, y: 24, w: 6.5, h: 17 },
    lgTop: 28.5, lgBot: 36.5,
    rgTop: 28.5, rgBot: 36.5,
    cx: 50, cy: 32.5, cr: 9.15,
  }

  const line = { stroke: '#1a3a2a', strokeWidth: 0.6, fill: 'none' }

  function shotFill(tipo) {
    if (tipo === 'gol')    return '#22d3ee'
    if (tipo === 'parado') return '#e2e8f0'
    return '#475569'
  }
  function shotR(tipo) {
    if (tipo === 'gol')    return 3.2
    if (tipo === 'parado') return 2.4
    return 2.0
  }

  const golesLocal     = disparos.filter(d => d.tipo === 'gol'    && d.equipo === 'local').length
  const golesVisitante = disparos.filter(d => d.tipo === 'gol'    && d.equipo === 'visitante').length
  const tirosPLocal    = disparos.filter(d => d.tipo === 'parado' && d.equipo === 'local').length
  const tirosPVis      = disparos.filter(d => d.tipo === 'parado' && d.equipo === 'visitante').length

  return (
    <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Mapa de Disparos</h4>
        <div className="flex items-center gap-3 text-[11px]">
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-cyan-400 inline-block ring-2 ring-cyan-400/30" /> Gol
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-slate-200 inline-block" /> Parado
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full bg-slate-600 inline-block" /> Fuera
          </span>
        </div>
      </div>

      {/* Shot summary */}
      <div className="grid grid-cols-2 gap-2 mb-3 text-[11px]">
        <div className="bg-slate-800/60 rounded-lg px-3 py-1.5 text-center">
          <span className="text-cyan-400 font-bold">{golesLocal}G · {tirosPLocal}P</span>
          <span className="text-slate-500 ml-1">Local</span>
        </div>
        <div className="bg-slate-800/60 rounded-lg px-3 py-1.5 text-center">
          <span className="text-violet-400 font-bold">{golesVisitante}G · {tirosPVis}P</span>
          <span className="text-slate-500 ml-1">Visitante</span>
        </div>
      </div>

      <div className="rounded-xl overflow-hidden border border-slate-700/30">
        <svg
          viewBox="0 0 100 65"
          className="w-full"
          style={{ background: 'linear-gradient(160deg, #071812 0%, #091f13 50%, #071812 100%)' }}
        >
          {/* Grass stripes */}
          {[0,1,2,3,4,5,6,7,8,9].map(i => (
            <rect key={i} x={1 + i*9.8} y={1} width={9.8} height={63}
              fill={i % 2 === 0 ? '#0a2016' : '#091a12'} opacity={0.6} />
          ))}

          {/* Pitch lines */}
          <rect x={lp.border.x} y={lp.border.y} width={lp.border.w} height={lp.border.h} {...line} />
          <line x1={lp.cx} y1={1} x2={lp.cx} y2={64} {...line} />
          <circle cx={lp.cx} cy={lp.cy} r={lp.cr} {...line} />
          <circle cx={lp.cx} cy={lp.cy} r={0.7} fill="#1a3a2a" />

          <rect x={lp.lpa.x} y={lp.lpa.y} width={lp.lpa.w} height={lp.lpa.h} {...line} />
          <rect x={lp.lga.x} y={lp.lga.y} width={lp.lga.w} height={lp.lga.h} {...line} />
          <rect x={lp.rpa.x} y={lp.rpa.y} width={lp.rpa.w} height={lp.rpa.h} {...line} />
          <rect x={lp.rga.x} y={lp.rga.y} width={lp.rga.w} height={lp.rga.h} {...line} />

          {/* Goals */}
          <rect x={-1} y={lp.lgTop} width={2} height={lp.lgBot - lp.lgTop}
            stroke="#1a3a2a" strokeWidth={0.5} fill="#051008" />
          <rect x={99} y={lp.rgTop} width={2} height={lp.rgBot - lp.rgTop}
            stroke="#1a3a2a" strokeWidth={0.5} fill="#051008" />

          {/* Penalty spots */}
          <circle cx={12} cy={lp.cy} r={0.6} fill="#1a3a2a" />
          <circle cx={88} cy={lp.cy} r={0.6} fill="#1a3a2a" />

          {/* Team labels */}
          <text x={25} y={62} textAnchor="middle" fill="#1a3a2a" fontSize={3.8} fontWeight="700">VISITANTE →</text>
          <text x={75} y={62} textAnchor="middle" fill="#1a3a2a" fontSize={3.8} fontWeight="700">← LOCAL</text>

          {/* Shots */}
          {disparos.map((d, i) => (
            <g key={i}>
              {d.tipo === 'gol' && (
                <>
                  <circle cx={d.x} cy={d.y} r={shotR(d.tipo) + 3.5} fill="#22d3ee" fillOpacity={0.08} />
                  <circle cx={d.x} cy={d.y} r={shotR(d.tipo) + 1.5} fill="#22d3ee" fillOpacity={0.18} />
                </>
              )}
              <circle
                cx={d.x} cy={d.y}
                r={shotR(d.tipo)}
                fill={shotFill(d.tipo)}
                stroke={d.tipo === 'gol' ? '#0891b2' : d.tipo === 'parado' ? '#94a3b8' : '#334155'}
                strokeWidth={0.5}
                fillOpacity={d.tipo === 'fuera' ? 0.75 : 1}
              />
            </g>
          ))}
        </svg>
      </div>
    </div>
  )
}

/* ══════════════════════════════════════════════════════
   PLAYER TABLE
══════════════════════════════════════════════════════ */
function PlayerTable({ jugadores, local, visitante }) {
  const localPlayers    = jugadores.filter(j => j.equipo === 'local').sort((a, b) => b.nota - a.nota)
  const visitPlayers = jugadores.filter(j => j.equipo === 'visitante').sort((a, b) => b.nota - a.nota)

  function TeamSection({ players, equipo }) {
    return (
      <>
        <tr>
          <td colSpan={7} className="pt-3 pb-1">
            <div className="flex items-center gap-2">
              <div
                className="px-2 py-0.5 rounded-full text-[10px] font-bold"
                style={{ background: `${equipo.color}18`, color: equipo.color, border: `1px solid ${equipo.color}30` }}
              >
                {equipo.abrev}
              </div>
              <span className="text-xs font-semibold text-slate-300">{equipo.nombre}</span>
            </div>
          </td>
        </tr>
        {players.map((j, i) => (
          <tr key={i} className="border-t border-slate-800/70 hover:bg-slate-800/20 transition-colors">
            <td className="py-2 pl-1">
              <div className="flex items-center gap-2">
                <div
                  className="w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-black shrink-0"
                  style={{ background: `${equipo.color}18`, color: equipo.color }}
                >
                  {initials(j.nombre)}
                </div>
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-white truncate">{j.nombre}</div>
                  <div className="text-[10px] text-slate-500">{j.pos}</div>
                </div>
              </div>
            </td>
            <td className="text-center text-slate-400 text-[11px] tabular-nums">{j.mins}'</td>
            <td className="text-center font-bold text-[11px] tabular-nums text-white">{j.goles}</td>
            <td className="text-center text-[11px] tabular-nums text-slate-400 hidden sm:table-cell">{j.asis}</td>
            <td className="text-center text-[11px] tabular-nums text-slate-400 hidden sm:table-cell">{j.xG.toFixed(2)}</td>
            <td className="text-center pr-1">
              <span
                className="text-sm font-black tabular-nums"
                style={{ color: notaColor(j.nota) }}
              >
                {j.nota.toFixed(1)}
              </span>
            </td>
          </tr>
        ))}
      </>
    )
  }

  return (
    <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4 overflow-x-auto">
      <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
        Rendimiento individual
      </h4>
      <table className="w-full text-xs min-w-[280px]">
        <thead>
          <tr className="text-slate-600 text-[10px] uppercase tracking-wider">
            <th className="text-left pb-1 pl-1">Jugador</th>
            <th className="text-center pb-1">Min</th>
            <th className="text-center pb-1">G</th>
            <th className="text-center pb-1 hidden sm:table-cell">A</th>
            <th className="text-center pb-1 hidden sm:table-cell">xG</th>
            <th className="text-center pb-1 pr-1">Nota</th>
          </tr>
        </thead>
        <tbody>
          <TeamSection players={localPlayers}   equipo={local} />
          <TeamSection players={visitPlayers} equipo={visitante} />
        </tbody>
      </table>
    </div>
  )
}

/* ══════════════════════════════════════════════════════
   XG SUMMARY BAR (top of detail)
══════════════════════════════════════════════════════ */
function XGSummary({ xG, local, visitante }) {
  const max = Math.max(xG.local, xG.visitante, 2)
  const lPct = (xG.local  / max) * 100
  const vPct = (xG.visitante / max) * 100
  const lWins = xG.local > xG.visitante

  return (
    <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4">
      <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Expected Goals (xG)</h4>
      <div className="flex flex-col gap-3">
        <div>
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-xs text-slate-400">{local.nombre}</span>
            <span className={`text-xl font-black tabular-nums ${lWins ? 'text-cyan-400' : 'text-slate-300'}`}>
              {xG.local.toFixed(2)}
            </span>
          </div>
          <div className="h-2.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${lWins ? 'bg-cyan-400' : 'bg-slate-500'}`}
              style={{ width: `${lPct}%` }}
            />
          </div>
        </div>
        <div>
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-xs text-slate-400">{visitante.nombre}</span>
            <span className={`text-xl font-black tabular-nums ${!lWins ? 'text-violet-400' : 'text-slate-300'}`}>
              {xG.visitante.toFixed(2)}
            </span>
          </div>
          <div className="h-2.5 bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-700 ${!lWins ? 'bg-violet-400' : 'bg-slate-500'}`}
              style={{ width: `${vPct}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

/* ══════════════════════════════════════════════════════
   MATCH DETAIL
══════════════════════════════════════════════════════ */
function MatchDetail({ partido }) {
  const { local, visitante, xG, stats: s, timeline, xgTimeline, disparos, jugadores, estadio } = partido

  const statRows = [
    { label: 'Posesión',       local: s.posesion.local,    visitante: s.posesion.visitante,    suffix: '%' },
    { label: 'Tiros totales',  local: s.tirosTotal.local,  visitante: s.tirosTotal.visitante,  suffix: '' },
    { label: 'Tiros a puerta', local: s.tirosPuerta.local, visitante: s.tirosPuerta.visitante, suffix: '' },
    { label: 'Córners',        local: s.corners.local,     visitante: s.corners.visitante,     suffix: '' },
    { label: 'Faltas',         local: s.faltas.local,      visitante: s.faltas.visitante,      suffix: '', invert: true },
    { label: 'Amarillas',      local: s.amarillas.local,   visitante: s.amarillas.visitante,   suffix: '', invert: true },
    { label: 'Rojas',          local: s.rojas.local,       visitante: s.rojas.visitante,       suffix: '', invert: true },
    { label: 'Fueras de juego',local: s.fuerasJuego.local, visitante: s.fuerasJuego.visitante, suffix: '', invert: true },
  ]

  return (
    <div className="border-t border-slate-800 animate-fade-up">
      <div className="p-4 sm:p-5 flex flex-col gap-5">

        {/* Estadio */}
        <p className="text-xs text-slate-500 text-center">{estadio}</p>

        {/* Timeline */}
        <MatchTimeline events={timeline} />

        {/* xG acumulado */}
        <XGChart
          xgTimeline={xgTimeline}
          localNombre={local.nombre}
          visitanteNombre={visitante.nombre}
        />

        {/* xG summary bars */}
        <XGSummary xG={xG} local={local} visitante={visitante} />

        {/* Estadísticas detalladas */}
        <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-bold text-cyan-400">{local.abrev}</span>
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Estadísticas</h4>
            <span className="text-xs font-bold text-violet-400">{visitante.abrev}</span>
          </div>
          <div className="flex flex-col gap-3">
            {statRows.map(row => (
              <div key={row.label}>
                <p className="text-[10px] text-slate-500 text-center mb-1">{row.label}</p>
                <StatRow {...row} />
              </div>
            ))}
          </div>
        </div>

        {/* Shot map */}
        <ShotMap disparos={disparos} />

        {/* Player table */}
        <PlayerTable jugadores={jugadores} local={local} visitante={visitante} />

      </div>
    </div>
  )
}

/* ══════════════════════════════════════════════════════
   MATCH CARD
══════════════════════════════════════════════════════ */
function MatchCard({ partido, expanded, onToggle }) {
  const { local, visitante, resultado, fecha, hora, estado } = partido
  const jugado = estado === 'jugado'

  return (
    <div
      className={`rounded-2xl border transition-all duration-200 overflow-hidden
        ${expanded
          ? 'border-cyan-500/40 bg-slate-900 shadow-lg shadow-cyan-950/30'
          : 'border-slate-800 bg-slate-900 hover:border-slate-700 hover:bg-slate-800/60 hover:scale-[1.005]'
        }`}
    >
      <button onClick={onToggle} className="w-full text-left p-4 sm:p-5">
        <div className="flex items-center gap-3 sm:gap-4">

          {/* Local */}
          <div className="flex-1 flex items-center gap-2 sm:gap-3 justify-end">
            <span className="text-sm sm:text-base font-semibold text-white text-right leading-tight hidden sm:block">
              {local.nombre}
            </span>
            <span className="text-sm font-bold text-white sm:hidden">{local.abrev}</span>
            <div
              className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center font-black text-xs shrink-0"
              style={{ background: `${local.color}18`, color: local.color, border: `1.5px solid ${local.color}40` }}
            >
              {local.abrev}
            </div>
          </div>

          {/* Score */}
          <div className="flex flex-col items-center shrink-0 min-w-[64px]">
            {jugado ? (
              <div className="flex items-center gap-1.5">
                <span className="text-2xl font-black tabular-nums text-white">{resultado.local}</span>
                <span className="text-lg font-bold text-slate-600">–</span>
                <span className="text-2xl font-black tabular-nums text-white">{resultado.visitante}</span>
              </div>
            ) : (
              <span className="text-lg font-black text-cyan-400">{hora}</span>
            )}
            <span className={`text-[10px] font-medium mt-0.5 px-2 py-0.5 rounded-full ${
              jugado ? 'text-slate-500 bg-slate-800' : 'text-cyan-400 bg-cyan-400/10'
            }`}>
              {jugado ? 'FIN' : 'PENDIENTE'}
            </span>
          </div>

          {/* Visitante */}
          <div className="flex-1 flex items-center gap-2 sm:gap-3">
            <div
              className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl flex items-center justify-center font-black text-xs shrink-0"
              style={{ background: `${visitante.color}18`, color: visitante.color, border: `1.5px solid ${visitante.color}40` }}
            >
              {visitante.abrev}
            </div>
            <span className="text-sm sm:text-base font-semibold text-white leading-tight hidden sm:block">
              {visitante.nombre}
            </span>
            <span className="text-sm font-bold text-white sm:hidden">{visitante.abrev}</span>
          </div>

          {/* Chevron */}
          <div className="shrink-0 ml-1">
            <svg
              className={`w-4 h-4 text-slate-500 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
              fill="none" stroke="currentColor" viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>

        <div className="flex justify-center mt-2">
          <span className="text-[11px] text-slate-600">{fecha} · {hora}</span>
        </div>
      </button>

      {expanded && jugado    && <MatchDetail partido={partido} />}
      {expanded && !jugado && (
        <div className="border-t border-slate-800 px-5 py-6 text-center text-sm text-slate-500">
          Partido no disputado todavía
        </div>
      )}
    </div>
  )
}

/* ══════════════════════════════════════════════════════
   PAGE
══════════════════════════════════════════════════════ */
export default function Partidos() {
  const [tab,        setTab]        = useState('directo')
  const [expanded,   setExpanded]   = useState(null)
  const [selectedId, setSelectedId] = useState('d2')   // por defecto el partido en min 67

  const toggle      = (id) => setExpanded(prev => prev === id ? null : id)
  const toggleLive  = (id) => setSelectedId(prev => prev === id ? null : id)
  const selectedPartido = DIRECTO.find(p => p.id === selectedId) ?? null

  const goles   = PARTIDOS.reduce((acc, p) => acc + p.resultado.local + p.resultado.visitante, 0)
  const xGTotal = PARTIDOS.reduce((acc, p) => acc + p.xG.local + p.xG.visitante, 0)

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
          Partidos <span className="text-cyan-400">LaLiga</span>
        </h1>
        <p className="text-sm text-slate-500 mt-1">Temporada 2024/25</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 p-1 bg-slate-900 border border-slate-800 rounded-xl w-fit mb-6">
        <button
          onClick={() => setTab('directo')}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold
                      transition-all duration-150 ${
            tab === 'directo'
              ? 'bg-cyan-400 text-slate-950 shadow-sm'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <span className={`w-2 h-2 rounded-full shrink-0 ${
            tab === 'directo' ? 'bg-slate-950 animate-pulse' : 'bg-emerald-400 animate-pulse'
          }`} />
          En directo
          <span className={`text-[10px] font-black px-1.5 py-0.5 rounded-full ${
            tab === 'directo' ? 'bg-slate-950/30' : 'bg-emerald-400/20 text-emerald-400'
          }`}>
            {DIRECTO.length}
          </span>
        </button>
        <button
          onClick={() => setTab('jornada')}
          className={`px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-150 ${
            tab === 'jornada'
              ? 'bg-cyan-400 text-slate-950 shadow-sm'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          Jornada 35
        </button>
      </div>

      {/* ══════════ EN DIRECTO */}
      {tab === 'directo' && (
        <div className="animate-fade-in">
          <div className={`grid gap-5 ${
            selectedPartido
              ? 'grid-cols-1 lg:grid-cols-[340px_1fr]'
              : 'grid-cols-1 sm:grid-cols-3'
          }`}>

            {/* Lista partidos en directo */}
            <div className="flex flex-col gap-3">
              {DIRECTO.map((p, i) => (
                <div key={p.id} className="animate-fade-up" style={{ animationDelay: `${i * 70}ms` }}>
                  <LiveCard
                    partido={p}
                    selected={selectedId === p.id}
                    onClick={() => toggleLive(p.id)}
                  />
                </div>
              ))}
              <p className="text-xs text-slate-600 px-1">
                Haz clic en un partido para ver el detalle →
              </p>
            </div>

            {/* Panel detalle live */}
            {selectedPartido && <LiveDetailPanel partido={selectedPartido} />}
          </div>
        </div>
      )}

      {/* ══════════ JORNADA 35 */}
      {tab === 'jornada' && (
        <div className="animate-fade-in max-w-3xl">
          <div className="grid grid-cols-3 gap-3 mb-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-3 text-center">
              <p className="text-2xl font-black text-white tabular-nums">{PARTIDOS.length}</p>
              <p className="text-[11px] text-slate-500 mt-0.5">Partidos</p>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-3 text-center">
              <p className="text-2xl font-black text-cyan-400 tabular-nums">{goles}</p>
              <p className="text-[11px] text-slate-500 mt-0.5">Goles</p>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-3 text-center">
              <p className="text-2xl font-black text-violet-400 tabular-nums">{xGTotal.toFixed(1)}</p>
              <p className="text-[11px] text-slate-500 mt-0.5">xG total</p>
            </div>
          </div>
          <div className="flex flex-col gap-3">
            {PARTIDOS.map((partido, i) => (
              <div key={partido.id} className="animate-fade-up" style={{ animationDelay: `${i * 50}ms` }}>
                <MatchCard
                  partido={partido}
                  expanded={expanded === partido.id}
                  onToggle={() => toggle(partido.id)}
                />
              </div>
            ))}
          </div>
        </div>
      )}

    </main>
  )
}
