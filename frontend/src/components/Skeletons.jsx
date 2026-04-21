// ─── Primitive ────────────────────────────────────────────────────────────────
function Bone({ className = '' }) {
  return <div className={`skeleton rounded ${className}`} />
}

// ─── Home: grid de player cards ───────────────────────────────────────────────
export function PlayerCardSkeleton() {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5">
      {/* Avatar + nombre */}
      <div className="flex items-start gap-3 mb-4">
        <Bone className="w-12 h-12 rounded-xl shrink-0" />
        <div className="flex-1 space-y-2 pt-1">
          <Bone className="h-4 w-3/4 rounded-full" />
          <Bone className="h-3 w-1/2 rounded-full" />
        </div>
      </div>
      {/* Métrica rows */}
      <div className="space-y-3 mb-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="flex items-center gap-2">
            <Bone className="h-3 flex-1 rounded-full" />
            <Bone className="h-2 w-20 rounded-full" />
            <Bone className="h-3 w-6 rounded" />
          </div>
        ))}
      </div>
      {/* Rate strip */}
      <div className="grid grid-cols-4 gap-2 pt-3 border-t border-slate-800/60">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="flex flex-col items-center gap-1.5">
            <Bone className="h-2 w-full rounded-full" />
            <Bone className="h-4 w-8 rounded" />
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Jugador: página completa ──────────────────────────────────────────────────
export function JugadorSkeleton() {
  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Volver */}
      <Bone className="h-4 w-24 rounded-full" />

      {/* Header card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8">
        <div className="flex flex-col sm:flex-row gap-6">
          <Bone className="w-20 h-20 rounded-2xl shrink-0" />
          <div className="flex-1 space-y-3">
            <Bone className="h-8 w-56 rounded-xl" />
            <Bone className="h-4 w-40 rounded-full" />
            <div className="flex gap-2 pt-1">
              {[...Array(5)].map((_, i) => (
                <Bone key={i} className="h-6 w-14 rounded-full" />
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Stat pills 2×2 */}
      <div>
        <Bone className="h-3 w-28 rounded-full mb-3" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="bg-slate-900 border border-slate-800 rounded-2xl px-5 py-4 space-y-2">
              <Bone className="h-3 w-16 rounded-full" />
              <Bone className="h-8 w-12 rounded-lg" />
            </div>
          ))}
        </div>
      </div>

      {/* Bar chart */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
        <Bone className="h-3 w-56 rounded-full mb-6" />
        <Bone className="h-[200px] w-full rounded-xl" />
      </div>

      {/* Radar + métricas */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <Bone className="h-3 w-48 rounded-full mb-4" />
          <Bone className="h-[220px] w-full rounded-xl" />
        </div>
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-1">
          <Bone className="h-3 w-32 rounded-full mb-5" />
          {[...Array(9)].map((_, i) => (
            <div key={i} className="flex items-center gap-3 py-2.5 border-b border-slate-800/40 last:border-0">
              <Bone className="h-3 flex-1 rounded-full" />
              <Bone className="h-2 w-28 rounded-full" />
              <Bone className="h-3 w-8 rounded" />
            </div>
          ))}
        </div>
      </div>
    </main>
  )
}

// ─── Scouting: cards de jugadores similares + radares ─────────────────────────
export function ScoutingSkeleton() {
  return (
    <>
      {/* Similar cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="bg-slate-900 border border-slate-800 rounded-2xl p-5 space-y-3">
            <div className="flex items-start justify-between">
              <Bone className="w-7 h-7 rounded-lg" />
              <Bone className="h-4 w-24 rounded-full" />
            </div>
            <Bone className="h-5 w-3/4 rounded-lg" />
            <Bone className="h-3 w-1/2 rounded-full" />
            <Bone className="h-3 w-1/3 rounded-full" />
          </div>
        ))}
      </div>

      {/* Radar block */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 mb-6">
        <Bone className="h-3 w-44 rounded-full mb-4" />
        {/* Legend */}
        <div className="flex gap-4 mb-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="flex items-center gap-2">
              <Bone className="w-2.5 h-2.5 rounded-full" />
              <Bone className="h-3 w-20 rounded-full" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Bone key={i} className="h-[180px] rounded-xl" />
          ))}
        </div>
      </div>
    </>
  )
}

// ─── Insights: grid de insight cards ──────────────────────────────────────────
export function InsightsSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
          {/* Icon + título */}
          <div className="flex gap-3 items-start">
            <Bone className="w-10 h-10 rounded-xl shrink-0" />
            <div className="flex-1 space-y-2 pt-1">
              <Bone className="h-4 w-full rounded-full" />
              <Bone className="h-3 w-2/3 rounded-full" />
            </div>
          </div>
          {/* Big stat */}
          <Bone className="h-16 w-full rounded-xl" />
          {/* Descripción */}
          <div className="space-y-2">
            <Bone className="h-3 w-full rounded-full" />
            <Bone className="h-3 w-4/5 rounded-full" />
          </div>
          {/* Footer */}
          <Bone className="h-3 w-2/5 rounded-full mt-auto" />
        </div>
      ))}
    </div>
  )
}
