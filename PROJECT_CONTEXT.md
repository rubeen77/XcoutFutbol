# PROJECT CONTEXT - Xcout / WebXcout

Documento generado tras analizar el proyecto local. Objetivo: servir como contexto de continuidad para otro asistente de IA antes de tocar codigo.

## 1. Resumen general

Xcout es una aplicacion de analitica de futbol orientada a scouting, comparacion de jugadores, seguimiento de ligas y generacion de insights. El producto combina datos de jugadores, equipos, partidos, clasificaciones, valores de mercado y analisis narrativo para presentar una experiencia en espanol con visualizaciones tipo dashboard.

El problema que resuelve es centralizar datos futbolisticos dispersos en varias fuentes publicas (FBref, Understat, Sofascore, Transfermarkt, API-Football) y convertirlos en una interfaz usable para:

- consultar jugadores y metricas avanzadas;
- comparar perfiles;
- ver rankings y curiosidades;
- revisar equipos, plantillas y clasificaciones;
- seguir partidos y detalles;
- generar resumenes de jornada con IA;
- captar leads desde una landing/waitlist.

El estado actual parece de producto en desarrollo avanzado, con varias ligas cargadas o parcialmente cargadas, pero con bastante deuda en scrapers, configuracion y normalizacion.

## 2. Stack tecnico completo

### Backend

- Python.
- FastAPI.
- Supabase Python client (`supabase`).
- APScheduler para tareas cron.
- Pydantic.
- Dotenv para `backend/.env`.
- Anthropic SDK para analisis de jornada con Claude.
- Pandas.
- soccerdata para FBref y Understat.
- requests / curl_cffi / cloudscraper para APIs y scraping.
- BeautifulSoup / lxml para Transfermarkt y paginas HTML.
- Playwright en algunos scrapers directos de FBref.

Nota importante: `backend/requirements.txt` esta vacio en esta copia. Las dependencias reales se infieren por imports, no por un lockfile backend.

### Frontend

- React 18.
- Vite 5.
- React Router DOM.
- Tailwind CSS.
- Recharts.
- Supabase JS en la landing.
- API propia via `fetch` contra `http://localhost:8001`.

### Base de datos / servicios

- Supabase como base de datos principal y tambien como backend directo para la waitlist desde frontend.
- Variables necesarias detectadas:
  - `SUPABASE_URL`
  - `SUPABASE_KEY`
  - `ANTHROPIC_API_KEY`
  - `VITE_SUPABASE_URL`
  - `VITE_SUPABASE_ANON_KEY`

### Fuentes externas

- FBref via `soccerdata` y scraping directo.
- Understat via `soccerdata`.
- Sofascore API publica.
- Transfermarkt.es via `cloudscraper`.
- API-Football en un scraper auxiliar.

## 3. Estructura real de carpetas y archivos importantes

```text
.
├── backend/
│   ├── main.py
│   ├── requirements.txt              # vacio
│   ├── database/
│   │   └── supabase_client.py
│   ├── routers/
│   │   ├── players.py
│   │   ├── teams.py
│   │   ├── matches.py
│   │   ├── insights.py
│   │   ├── leagues.py
│   │   ├── waitlist.py
│   │   ├── scouting.py               # vacio
│   │   └── club.py                   # vacio
│   ├── scheduler/
│   │   └── jobs.py
│   ├── ai/
│   │   └── insights_generator.py
│   ├── analysis/
│   │   ├── similarity.py
│   │   ├── reports.py
│   │   ├── performance.py
│   │   └── insights.py
│   ├── scrapers/
│   │   ├── fbref_scraper.py
│   │   ├── fbref_premier.py
│   │   ├── fbref_bundesliga.py
│   │   ├── fbref_seriea.py
│   │   ├── fbref_ligue1.py
│   │   ├── fbref_champions.py
│   │   ├── *_historico.py
│   │   ├── sofascore_*.py
│   │   ├── transfermarkt_*.py
│   │   ├── escudos_*.py
│   │   ├── clasificacion_scraper.py
│   │   ├── understat_scraper.py
│   │   ├── traspasos_scraper.py
│   │   └── fix_*.py / debug helpers
│   └── notebooks/
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   ├── index.css
│   │   ├── services/api.js
│   │   ├── contexts/LigaContext.jsx
│   │   ├── pages/
│   │   │   ├── Landing.jsx
│   │   │   ├── Home.jsx
│   │   │   ├── Jugador.jsx
│   │   │   ├── Scouting.jsx
│   │   │   ├── Equipos.jsx
│   │   │   ├── EquipoDetalle.jsx
│   │   │   ├── Partidos.jsx
│   │   │   ├── Insights.jsx
│   │   │   └── Precios.jsx
│   │   ├── components/
│   │   │   ├── Navbar.jsx
│   │   │   ├── Footer.jsx
│   │   │   ├── PlayerCard.jsx
│   │   │   ├── RadarChart.jsx
│   │   │   ├── HeatMap.jsx
│   │   │   ├── InsightCard.jsx
│   │   │   ├── Skeletons.jsx
│   │   │   └── UCLEliminatorias.jsx
│   │   ├── data/                     # datos fallback/locales
│   │   └── hooks/useCountUp.js
│   └── public/
├── WebXcout/frontend/                 # copia anidada parcial del frontend
└── downloaded_files/
```

La carpeta `WebXcout/frontend/` parece una copia antigua/paralela del frontend. El frontend activo real parece ser `frontend/`.

## 4. Flujo de datos completo

### Scrapers

1. Los scrapers descargan datos desde FBref, Understat, Sofascore, Transfermarkt o API-Football.
2. Normalizan nombres de equipos/jugadores con helpers locales tipo `_norm`.
3. Insertan o actualizan datos en Supabase:
   - `ligas`
   - `equipos`
   - `jugadores`
   - `estadisticas_jugador`
   - `partidos`
   - `valor_mercado_historia`
   - `eliminatorias`
   - `traspasos`
4. Cada liga tiene scripts propios, no hay aun un motor generico multi-liga.
5. Varios scripts requieren aliases manuales para resolver nombres entre fuentes.

### Backend FastAPI

1. `backend/main.py` crea la app FastAPI.
2. Carga routers:
   - `/jugadores`
   - `/equipos`
   - `/partidos`
   - `/insights`
   - `/leagues`
   - `/waitlist`
3. Usa CORS abierto.
4. Inicializa APScheduler en el lifespan.
5. Consulta Supabase directamente desde cada router.
6. En algunos endpoints transforma la respuesta para el frontend.

### Supabase

Supabase es la fuente de verdad. El backend no tiene ORM ni migraciones visibles. Las relaciones se usan mediante selects anidados de Supabase/PostgREST:

- `jugadores.equipo_id -> equipos.id`
- `equipos.liga_id -> ligas.id`
- `estadisticas_jugador.jugador_id -> jugadores.id`
- `estadisticas_jugador.liga_id -> ligas.id`
- `partidos.equipo_local -> equipos.id`
- `partidos.equipo_visitante -> equipos.id`
- `partidos.liga_id -> ligas.id`
- `valor_mercado_historia.jugador_id -> jugadores.id`

### Frontend React

1. `App.jsx` define rutas.
2. `LigaContext.jsx` carga ligas desde `/leagues` y mantiene `ligaId`.
3. `services/api.js` llama al backend en `http://localhost:8001`.
4. Cada pagina pide datos por API y renderiza visualizaciones.
5. La landing usa Supabase JS directamente para insertar emails en `lista_espera`, aunque tambien existe endpoint backend `/waitlist`.

## 5. Endpoints del backend

### Sistema / admin

- `GET /health`
  - Devuelve `{ status: "ok", version: "1.0.0" }`.

- `GET /api/scheduler/estado`
  - Devuelve si APScheduler esta activo y lista jobs con `id`, `proximo_run`, `trigger`.

- `POST /api/scheduler/forzar-actualizacion`
  - Lanza actualizacion semanal en un thread.
  - Devuelve mensaje de inicio.

- `GET /api/admin/actualizar-clasificaciones?liga_id=...`
  - Lanza `clasificacion_scraper.run()` en background.
  - Si no hay `liga_id`, actualiza todas las ligas configuradas.

### Ligas

- `GET /leagues`
  - Lee `ligas`.
  - Devuelve `{ ligas: [{ id, nombre, pais }] }`.

### Jugadores

- `GET /jugadores`
  - Query params: `liga_id`, `equipo_id`, `posicion`, `min_goles`, `max_valor_mercado`, `temporada`, `orden`, `orden_dir`, `limit`, `offset`.
  - Parte desde `estadisticas_jugador`, une `jugadores` y `equipos`.
  - Devuelve `{ total, jugadores }`, con cada jugador aplanado y `stats`.
  - Limitacion: algunos filtros son post-fetch; paginacion ocurre tras filtrar en Python.

- `GET /jugadores/count?temporada=2526`
  - Cuenta filas en `estadisticas_jugador`.
  - Devuelve `{ count }`.

- `GET /jugadores/top-scorer?liga_id=1&temporada=2526`
  - Devuelve el maximo goleador de una liga.
  - Shape: `{ jugador: { ...datos, equipo, goles, asistencias, xg, xa, minutos } }`.

- `GET /jugadores/ranking?metrica=goles&temporada=2526&limit=20&posicion=&liga_id=`
  - Ranking por metrica.
  - Metricas validas: `goles`, `asistencias`, `xg`, `xa`, `ga_por_90`, `valor_mercado`, `minutos`.
  - Devuelve `{ metrica, temporada, ranking }`.
  - Si `metrica=valor_mercado`, consulta `jugadores`; si no, `estadisticas_jugador`.

- `GET /jugadores/{jugador_id}`
  - Perfil completo.
  - Devuelve jugador con equipo, lista de `estadisticas_jugador` y `valor_mercado_historia`.

### Equipos

- `GET /equipos?liga_id=1&temporada=2526`
  - Lista equipos de una liga ordenados por clasificacion.
  - Incluye `ligas(nombre,pais)` y `top_goleadores`.
  - Devuelve `{ total, equipos }`.

- `GET /equipos/{equipo_id}/detalle?temporada=2526`
  - Para pagina detalle.
  - Devuelve `{ equipo, clasificacion, plantilla }`.

- `GET /equipos/{equipo_id}?temporada=2526`
  - Endpoint legacy.
  - Devuelve equipo, plantilla, totales de temporada, partidos como local y visitante.

### Partidos

- `GET /partidos`
  - Query params: `jornada`, `liga_id`, `temporada`, `estado`, `equipo_id`.
  - Devuelve `{ total, partidos }`.
  - Une local/visitante con `equipos`.
  - `equipo_id` se filtra post-fetch.

- `GET /partidos/recientes?liga_id=1&temporada=2526&limit=4`
  - Ultimos partidos con goles no nulos.
  - Devuelve `{ partidos }`.

- `GET /partidos/count?temporada=2526`
  - Cuenta partidos.
  - Devuelve `{ count }`.

- `GET /partidos/eliminatorias?liga_id=28&temporada=2526`
  - Lee `eliminatorias`, agrupa por ronda.
  - Devuelve `{ rondas: [{ ronda, cruces }] }`.

- `GET /partidos/{partido_id}`
  - Devuelve detalle de partido.
  - Si tiene `sofascore_id`, intenta cargar eventos en tiempo real desde Sofascore.
  - Shape: partido + `{ eventos }`.

### Insights

- `GET /insights/rankings?temporada=2526&liga_id=1`
  - Devuelve rankings top 5: `goleadores`, `asistentes`, `sobre_xg`, `regates`, `recuperaciones`, `g90`.

- `GET /insights/datos-curiosos?temporada=2526&liga_id=1`
  - Calcula curiosidades desde jugadores y partidos:
    - mejor sobre xG;
    - peor xG;
    - jornada con mas goles;
    - mejor equipo en casa;
    - mejor equipo fuera.

- `GET /insights/quiz?temporada=2526&liga_id=1`
  - Devuelve jugador aleatorio con stats y opciones de respuesta.

- `POST /insights/generar-analisis`
  - Body: `{ liga_id, jornada, temporada }`.
  - Genera o recupera analisis de jornada con Claude.

- `GET /insights/analisis?liga_id=1&temporada=2526`
  - Devuelve el analisis de jornada mas reciente:
  - `{ analisis: row | null }`.

### Waitlist

- `POST /waitlist`
  - Body: `{ email }`.
  - Inserta en `lista_espera` si no existe.
  - Devuelve `{ ok, message }`.

## 6. Tablas de Supabase usadas y relaciones

Tablas detectadas por uso en codigo:

- `ligas`
  - Campos usados: `id`, `nombre`, `pais`, `temporada_actual`.
  - Relacion: uno a muchos con `equipos`, `partidos`, `estadisticas_jugador`, `eliminatorias`.

- `equipos`
  - Campos usados: `id`, `nombre`, `liga_id`, `temporada`, `posicion_clasificacion`, `puntos`, `escudo_url`.
  - Relacion: pertenece a `ligas`; tiene muchos `jugadores`; aparece dos veces en `partidos` como local/visitante.

- `jugadores`
  - Campos usados: `id`, `nombre`, `posicion`, `edad`, `nacionalidad`, `foto_url`, `valor_mercado`, `equipo_id`.
  - Relacion: pertenece a `equipos`; tiene muchas `estadisticas_jugador`; tiene historial de valor.

- `estadisticas_jugador`
  - Campos usados: `jugador_id`, `temporada`, `liga_id`, `goles`, `asistencias`, `xg`, `xa`, `minutos`, `pases_completados`, `regates`, `presiones`, `recuperaciones`, `goles_por_90`, `asistencias_por_90`, `ga_por_90`, `portero_paradas`, `portero_goles_encajados`, `portero_paradas_pct`, `intercepciones`, `entradas`, `tiros_totales`, `tiros_a_puerta`.
  - Conflicto esperado: `jugador_id,temporada,liga_id`.

- `partidos`
  - Campos usados: `id`, `sofascore_id`, `liga_id`, `temporada`, `jornada`, `fecha`, `estado`, `equipo_local`, `equipo_visitante`, `goles_local`, `goles_visitante`, `xg_local`, `xg_visitante`.
  - Relaciones: `equipo_local` y `equipo_visitante` apuntan a `equipos`.

- `valor_mercado_historia`
  - Campos usados: `jugador_id`, `temporada`, `valor`, posiblemente `fecha`/historico segun scraper.
  - Relacion: pertenece a `jugadores`.

- `analisis_jornada`
  - Campos usados: `id`, `liga_id`, `temporada`, `jornada`, `titulo`, `contenido`, `generado_en`.
  - Conflicto esperado: `liga_id,temporada,jornada`.

- `eliminatorias`
  - Campos usados: `liga_id`, `temporada`, `ronda`, `orden` y todos los campos via `select("*")`.
  - Usada para Champions League.

- `lista_espera`
  - Campos usados: `id`, `email`, `fecha`, `origen`.
  - Usada por backend y tambien por frontend directo.

- `traspasos`
  - Usada por `traspasos_scraper.py`, no expuesta por API principal.

No hay archivos SQL/migraciones en el repo, asi que el schema exacto debe verificarse en Supabase antes de ampliar.

## 7. Scrapers existentes

### Scrapers principales por liga

- `fbref_scraper.py`
  - Fuente: FBref via soccerdata.
  - Liga: LaLiga (`liga_id=1`).
  - Carga: liga, equipos, jugadores, stats basicas, recuperaciones.
  - Limitacion: xG/xA no salen aqui; dependen de Understat; pases/regates se dejan para otros scrapers.

- `fbref_premier.py`
  - Fuente: Understat + FBref via soccerdata.
  - Liga: Premier League (`liga_id=24`).
  - Carga: xG/xA, porteros y updates de estadisticas.
  - Limitacion: parece updater parcial, no necesariamente carga completa desde cero.

- `premier_scraper.py`
  - Fuente: FBref/Understat/Transfermarkt segun codigo.
  - Liga: Premier League.
  - Carga mas amplia: equipos, jugadores, estadisticas, partidos y valores.
  - Limitacion: convive con `fbref_premier.py` y `transfermarkt_premier_full.py`; riesgo de solapamiento.

- `fbref_bundesliga.py`
  - Fuente: FBref + Understat.
  - Liga: Bundesliga (`liga_id=25`).
  - Carga: equipos, jugadores, stats basicas, porteros, xG inicial, misc, xG/xA Understat, partidos.
  - Limitacion: aliases manuales, delays, dependencia de columnas FBref.

- `fbref_seriea.py`
  - Fuente: FBref + Understat.
  - Liga: Serie A (`liga_id=26`).
  - Carga: equipos, jugadores, stats basicas, porteros, xG/xA, partidos.
  - Limitacion: normalizacion compleja por caracteres/nombres italianos.

- `fbref_ligue1.py`
  - Fuente: FBref + Understat + Transfermarkt.
  - Liga: Ligue 1 (`liga_id=27`).
  - Carga: historico, equipos, jugadores, stats, porteros, xG/xA, partidos, fotos y valores.
  - Limitacion: archivo muy grande, con historico activado por constante `INCLUIR_HISTORICO=True`; riesgo de reejecucion costosa.

- `fbref_champions.py`
  - Fuente: Sofascore como principal.
  - Liga: Champions League (`liga_id=28`).
  - Carga: equipos, jugadores, stats desde Sofascore.
  - Limitacion: Champions no sigue formato domestico; nombres/equipos cambian mas y hay logica separada.

### Sofascore

- `sofascore_scraper.py`
  - Fuente: Sofascore API.
  - Liga: LaLiga.
  - Carga: partidos del dia, estado, marcador y eventos en tiempo real.
  - Limitacion: hardcodeado a LaLiga (`tournament_id=8`, `DB_LIGA_ID=1`).

- `clasificacion_scraper.py`
  - Fuente: Sofascore standings.
  - Ligas: LaLiga, Premier, Bundesliga, Serie A, Ligue 1, Champions.
  - Carga: `posicion_clasificacion` y `puntos` en `equipos`.
  - Limitacion: usa primera tabla de standings; depende de season_id y aliases.

- `sofascore_jornadas_scraper.py`
  - Fuente: Sofascore.
  - Uso probable: partidos por jornada.
  - Carga: `partidos`.
  - Limitacion: necesita revisar configuracion por liga antes de extender.

- `sofascore_*_scraper.py`
  - Variantes para Bundesliga, Champions, Ligue 1, Premier, Serie A.
  - Cargan o completan estadisticas en `estadisticas_jugador`.
  - Limitacion: duplicacion alta y normalizacion manual.

- `sofascore_champions_partidos.py`, `sofascore_champions_detalle.py`, `sofascore_ligue1_partidos.py`
  - Especializados en partidos/detalles.
  - Limitacion: scripts de proposito especifico, no motor comun.

### Transfermarkt

- `transfermarkt_scraper.py`
  - Liga: LaLiga.
  - Fuente: Transfermarkt.es.
  - Carga: `foto_url`, `valor_mercado`, `valor_mercado_historia`.

- `transfermarkt_laliga_full.py`
  - Variante completa de LaLiga.

- `transfermarkt_premier_full.py`
  - Liga: Premier.
  - Carga: fotos y valor de mercado.

- `transfermarkt_bundesliga.py`
  - Liga: Bundesliga.
  - Carga: fotos y valor de mercado.

- `transfermarkt_seriea.py`
  - Liga: Serie A.
  - Carga: fotos y valor de mercado.

- `transfermarkt_champions.py`
  - Liga: Champions.
  - Usa lista hardcoded de 29 equipos UCL.
  - Limitacion importante: lista hardcoded puede quedar obsoleta y no cubre 36 equipos del formato actual si no se actualiza.

- `tm_historial_faltante.py`
  - Completa historial faltante.

### Escudos

- `escudos_scraper.py`, `escudos_premier.py`, `escudos_bundesliga.py`, `escudos_seriea.py`
  - Fuente: Transfermarkt CDN.
  - Carga: `escudo_url` en `equipos`.
  - Limitacion: por liga, con matching manual.

### Historicos y fixes

- `fbref_historico_scraper.py`
  - LaLiga historico 2020/21-2024/25.

- `fbref_premier_historico.py`, `fbref_bundesliga_historico.py`, `fbref_seriea_historico.py`
  - Historicos por liga.

- `fix_seriea_xg.py`, `fix_ligue1_xg.py`, `fix_nicolas_paz.py`, `fix_fotos_champions.py`
  - Scripts correctivos ad hoc.

### Problemas generales detectados en scrapers

- Mucho codigo duplicado por liga.
- IDs y temporadas hardcodeados.
- Aliases manuales dispersos.
- Dependencia fuerte de HTML/API externa sin tests.
- No hay pipeline orquestado unico.
- No hay capa comun de matching jugador/equipo.
- Algunos scripts son experimentales/debug y conviven con scripts productivos.
- Riesgo de sobrescritura entre fuentes si se ejecutan en orden incorrecto.
- Algunos comentarios dicen que una fuente sobrescribe a otra; esto debe respetarse.

## 8. Estado actual del frontend

### Rutas

- `/`
  - `Landing.jsx`
  - Landing comercial y waitlist.
  - Inserta email directamente en Supabase.

- `/jugadores`
  - `Home.jsx`
  - Dashboard principal de jugadores, filtros, rankings, hero, top scorer, ultimos partidos, analisis.

- `/jugador/:id`
  - `Jugador.jsx`
  - Perfil de jugador, metricas por temporada, radar, charts y valor de mercado.

- `/scouting`
  - `Scouting.jsx`
  - Comparador y similitud de jugadores en cliente.
  - Usa `getJugadores()`.

- `/equipos`
  - `Equipos.jsx`
  - Clasificacion y cards de equipos.
  - Incluye logica especial de zonas europeas/descenso y Champions.

- `/equipos/:id`
  - `EquipoDetalle.jsx`
  - Detalle equipo, clasificacion y plantilla.

- `/partidos`
  - `Partidos.jsx`
  - Lista por jornadas, modal de detalle, forma reciente, eventos si existen.
  - Para Champions usa componente `UCLEliminatorias`.

- `/insights`
  - `Insights.jsx`
  - Rankings, curiosidades, quiz y analisis IA.

- `/precios`
  - `Precios.jsx`
  - Pagina de planes/precios.

### Componentes importantes

- `Navbar.jsx`
  - Navegacion, selector de liga, health check contra `http://localhost:8001/health`.

- `PlayerCard.jsx`
  - Card de jugador para listados.

- `RadarChart.jsx`
  - Radar custom de jugador.

- `UCLEliminatorias.jsx`
  - Bracket/lista de eliminatorias Champions desde `/partidos/eliminatorias`.

- `Skeletons.jsx`
  - Estados de carga.

- `LigaContext.jsx`
  - Estado global de liga actual.
  - Fallback hardcodeado:
    - 1 LaLiga
    - 24 Premier League
    - 25 Bundesliga
    - 26 Serie A
    - 27 Ligue 1
    - 28 Champions League

### Llamadas API frontend

Todas estan en `frontend/src/services/api.js`:

- `getJugadores`
- `getJugador`
- `getRanking`
- `getEquipos`
- `getRankingLiga`
- `getEquipoDetalle`
- `getEquipoDetallePagina`
- `getPartidoDetalle`
- `getPartidosPorEquipo`
- `getAnalisisJornada`
- `generarAnalisis`
- `getInsightsRankings`
- `getInsightsDatosCuriosos`
- `getInsightsQuiz`
- `getPartidos`
- `getUltimosPartidos`
- `getLeagues`
- `getTopScorer`
- `getConteoJugadores`
- `getEliminatorias`
- `getConteoPartidos`

## 9. Funcionalidades ya terminadas

- Backend FastAPI con routers principales.
- Conexion Supabase centralizada.
- Listado de jugadores con filtros basicos.
- Rankings de jugadores.
- Perfil de jugador.
- Listado y detalle de equipos.
- Listado y detalle de partidos.
- Eventos de partido via Sofascore cuando hay `sofascore_id`.
- Insights basicos por liga.
- Quiz de jugador.
- Generacion/cache de analisis de jornada con Claude.
- Scheduler semanal de analisis, clasificaciones y actualizacion de datos.
- Landing y waitlist.
- Selector multi-liga en frontend.
- Soporte actual de ligas: LaLiga, Premier, Bundesliga, Serie A, Ligue 1 y Champions.
- Scrapers para stats, partidos, clasificacion, escudos, fotos y valores de mercado.

## 10. Funcionalidades pendientes

- Backend real para `/scouting` y `/club`: routers existen pero estan vacios.
- Motor generico de scrapers multi-liga.
- Migraciones/schema versionado de Supabase.
- Configuracion por entorno del `BASE_URL` frontend.
- Tests de backend y frontend.
- Manejo de errores mas uniforme en API.
- Paginacion server-side real en jugadores/partidos.
- Autenticacion/roles si el producto se monetiza.
- Unificar waitlist: frontend usa Supabase directo, backend tambien tiene endpoint.
- Soporte completo para nuevas ligas solicitadas:
  - Hypermotion
  - Portugal
  - Argentina
  - Brasil
  - Libertadores
- Normalizar zonas de clasificacion/descenso por liga en un archivo de configuracion, no hardcodeadas en componentes.
- Revisar y completar Champions: formato 36 equipos, eliminatorias y datos actuales.

## 11. Riesgos tecnicos importantes

- `backend/requirements.txt` vacio: dificil reproducir entorno.
- `frontend/src/services/api.js` usa `http://localhost:8001`, pero `backend/main.py` comenta arranque en puerto 8000.
- CORS abierto con `allow_origins=["*"]`.
- No hay migraciones SQL visibles.
- Scrapers dependen de HTML y APIs no oficiales.
- `Transfermarkt` y `FBref` pueden bloquear o cambiar estructura.
- Normalizacion de nombres fragil.
- Muchos upserts dependen de constraints concretos que no estan documentados en SQL.
- Posible desalineacion de temporadas (`2526`, `2025`, season_ids externos).
- Duplicacion de frontend en `WebXcout/frontend`.
- Codificacion mojibake visible en varios archivos/comentarios/textos (`Ã¡`, `â€”`, etc.).
- Landing escribe directo en Supabase desde cliente; revisar RLS y duplicados.
- Scheduler ejecuta scrapers pesados en el mismo proceso FastAPI.
- Varios scripts correctivos pueden pisar datos si se ejecutan sin entender el orden.

## 12. Deuda tecnica detectada

- Falta de gestor de dependencias backend.
- Ausencia de tests.
- Ausencia de README tecnico.
- Routers vacios incluidos en repo.
- Scrapers monoliticos y repetidos.
- Configuracion dispersa de IDs de liga, season IDs y aliases.
- Logica de negocio en frontend para zonas europeas/descenso.
- Filtros post-fetch en backend que no escalan.
- Sin modelos Pydantic de respuesta.
- Sin capa de servicios/repositorios entre routers y Supabase.
- Uso mezclado de datos fallback y API real.
- Comentarios y strings con problemas de encoding.
- Dependencia directa de `localhost` en frontend.
- No hay documentacion del schema de Supabase.

## 13. Recomendaciones para los proximos pasos

1. Crear un `README.md` tecnico minimo con comandos reales de arranque, puertos y variables.
2. Rellenar `backend/requirements.txt` o migrar a `pyproject.toml`.
3. Documentar el schema Supabase en `docs/schema.md` o una migracion SQL.
4. Crear una configuracion central de ligas:
   - `db_liga_id`
   - nombre
   - pais
   - temporada
   - fuente FBref/Understat/Sofascore/Transfermarkt
   - tournament IDs
   - reglas de clasificacion
   - aliases
5. Extraer helpers comunes de scrapers:
   - normalizacion;
   - matching equipo/jugador;
   - upsert batches;
   - parseo de valores;
   - rate limit.
6. Decidir puerto oficial backend y cambiar frontend a `VITE_API_BASE_URL`.
7. Implementar tests pequenos para routers con Supabase mockeado.
8. Evitar ejecutar historicos por defecto.
9. Separar scheduler de FastAPI si el proyecto crece.
10. Antes de nuevas ligas, estabilizar pipeline para una liga domestica usando una plantilla comun.

## 14. Que NO deberia tocarse todavia

- No reescribir el frontend antes de estabilizar el flujo de datos.
- No cambiar nombres de columnas Supabase sin migracion y actualizacion de todos los scrapers.
- No eliminar scripts `fix_*` o historicos hasta verificar si se usaron para datos actuales.
- No cambiar constraints de upsert (`nombre,equipo_id`, `jugador_id,temporada,liga_id`, etc.) sin revisar Supabase.
- No modificar el orden de fuentes xG/xA sin comprobar que Understat debe sobrescribir valores iniciales de FBref.
- No tocar `LigaContext` para nuevas ligas sin insertar primero las ligas/equipos/stats en Supabase.
- No mover la landing a usar `/waitlist` hasta revisar RLS y si el flujo actual esta en produccion.
- No activar historicos por defecto en nuevos scrapers.
- No ejecutar scrapers masivos sin copia/backup de Supabase.

## 15. Plan recomendado para anadir nuevas ligas

Ligas solicitadas:

- Hypermotion
- Portugal
- Argentina
- Brasil
- Libertadores

### Paso 0: preparar base comun

Antes de crear scripts nuevos, conviene crear una pequena matriz de configuracion por liga. Propuesta:

```python
LEAGUES = {
  "hypermotion": {
    "db_liga_id": <nuevo>,
    "nombre": "LaLiga Hypermotion",
    "pais": "Espana",
    "temporada": "2526",
    "fbref": "ESP-Segunda Division",
    "tm_code": "ES2",
    "sofascore_tournament_id": <buscar>,
  },
}
```

Tambien documentar constraints y crear filas en `ligas`.

### Hypermotion

Prioridad recomendada: alta, porque es similar a LaLiga y el publico objetivo probablemente la valora.

Plan:

1. Confirmar fuente disponible:
   - FBref/soccerdata para Segunda Division si existe como `ESP-Segunda Division`.
   - Sofascore para clasificacion y partidos.
   - Transfermarkt codigo probable `ES2`.
2. Copiar la estrategia de LaLiga, no la de Champions.
3. Crear scraper nuevo derivado del patron mas limpio.
4. Cargar:
   - `ligas`;
   - `equipos`;
   - `jugadores`;
   - `estadisticas_jugador`;
   - `partidos`;
   - `escudo_url`;
   - `valor_mercado`.
5. Ajustar reglas de clasificacion en frontend:
   - ascenso directo;
   - playoff;
   - descenso.

### Portugal

Prioridad recomendada: media-alta.

Plan:

1. Verificar nombre FBref/soccerdata para Primeira Liga.
2. Sofascore para standings/partidos.
3. Transfermarkt codigo probable `PO1`.
4. Crear aliases para clubes con nombres largos (`Sporting CP`, `Benfica`, `Porto`, etc.).
5. Reglas frontend:
   - Champions/Europa/Conference;
   - descenso/playoff segun formato vigente.

### Argentina

Prioridad recomendada: media, pero con cautela.

Riesgos:

- Formato de competicion puede ser menos estable.
- FBref/Understat pueden no tener cobertura equivalente.
- Calendario anual no encaja igual con `2526`.

Plan:

1. Decidir representacion de temporada: puede no ser `2526`.
2. Usar Sofascore/API-Football para partidos y clasificacion si FBref no cubre suficiente.
3. Cargar primero equipos y partidos.
4. Luego stats de jugadores si fuente fiable existe.
5. No forzar reglas europeas/descenso del frontend sin configuracion especifica.

### Brasil

Prioridad recomendada: media, similar a Argentina pero probablemente con mejor estructura de liga.

Plan:

1. Verificar disponibilidad FBref para Brasileirao Serie A.
2. Definir temporada anual (`2026` o equivalente interno).
3. Sofascore para standings y partidos.
4. Transfermarkt para valores/fotos si se necesita.
5. Adaptar UI a calendario anual y reglas CONMEBOL/descenso.

### Libertadores

Prioridad recomendada: despues de Brasil/Argentina, porque es competicion continental y se parece mas a Champions que a una liga domestica.

Plan:

1. Tratarla como competicion separada tipo Champions, no como liga domestica.
2. Usar Sofascore como fuente principal:
   - equipos;
   - jugadores;
   - partidos;
   - grupos/fase liga/eliminatorias segun formato.
3. Crear tabla/uso similar a `eliminatorias` si hay cruces.
4. Evitar depender de Transfermarkt hardcoded salvo para equipos principales.
5. Crear componente especifico si el formato no encaja con `Equipos.jsx`/`Partidos.jsx`.

### Orden recomendado de implementacion

1. Hypermotion.
2. Portugal.
3. Brasil.
4. Argentina.
5. Libertadores.

Razon: empezar por ligas mas parecidas al pipeline actual y dejar competiciones/formats mas especiales para cuando exista una abstraccion comun.

## CONTEXTO RESUMIDO PARA CHATGPT

Proyecto: Xcout/WebXcout, app de analitica de futbol en espanol. Backend FastAPI + Supabase; frontend React/Vite/Tailwind/Recharts. Scrapers Python cargan datos desde FBref, Understat, Sofascore y Transfermarkt. Frontend consume `http://localhost:8001` via `frontend/src/services/api.js`.

Carpetas clave: `backend/main.py`, `backend/routers/*`, `backend/scrapers/*`, `backend/scheduler/jobs.py`, `backend/ai/insights_generator.py`, `frontend/src/App.jsx`, `frontend/src/services/api.js`, `frontend/src/contexts/LigaContext.jsx`, `frontend/src/pages/*`.

Ligas actuales: LaLiga `1`, Premier `24`, Bundesliga `25`, Serie A `26`, Ligue 1 `27`, Champions `28`. Temporada comun actual: `2526`.

Tablas Supabase usadas: `ligas`, `equipos`, `jugadores`, `estadisticas_jugador`, `partidos`, `valor_mercado_historia`, `analisis_jornada`, `eliminatorias`, `lista_espera`, `traspasos`.

Endpoints principales: `/jugadores`, `/jugadores/ranking`, `/jugadores/{id}`, `/equipos`, `/equipos/{id}/detalle`, `/partidos`, `/partidos/{id}`, `/partidos/eliminatorias`, `/insights/rankings`, `/insights/datos-curiosos`, `/insights/quiz`, `/insights/analisis`, `/insights/generar-analisis`, `/leagues`, `/waitlist`, `/health`.

Frontend ya tiene paginas: landing, jugadores/home, perfil jugador, scouting, equipos, detalle equipo, partidos, insights y precios. `scouting.py` y `club.py` del backend estan vacios; scouting se calcula en cliente.

Riesgos: `backend/requirements.txt` esta vacio; no hay migraciones SQL; puerto backend inconsistente (`main.py` comenta 8000, frontend usa 8001); CORS abierto; scrapers duplicados por liga; aliases manuales; datos y season IDs hardcodeados; carpeta duplicada `WebXcout/frontend`; textos con problemas de encoding.

No tocar aun: schema Supabase, constraints de upsert, orden de fuentes xG/xA, scripts `fix_*`, historicos, ni reescribir frontend. Primero documentar dependencias, schema y configuracion de ligas.

Plan nuevas ligas: crear configuracion central de ligas y helpers comunes para scrapers. Implementar en orden Hypermotion, Portugal, Brasil, Argentina y Libertadores. Hypermotion/Portugal como ligas domesticas similares al pipeline actual; Brasil/Argentina requieren tratar temporada anual; Libertadores debe modelarse como competicion continental tipo Champions con flujo Sofascore y eliminatorias.
