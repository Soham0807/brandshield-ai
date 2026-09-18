/** Animated background: drifting aurora blobs + faint grid + film grain. */
export default function Backdrop() {
  const blobs = [
    { c: 'rgba(249,115,22,.30)', size: 620, top: '-14%', left: '-8%', delay: '0s', dur: '26s' },
    { c: 'rgba(168,85,247,.22)', size: 520, top: '18%', left: '62%', delay: '-8s', dur: '32s' },
    { c: 'rgba(34,211,238,.18)', size: 460, top: '64%', left: '12%', delay: '-16s', dur: '38s' },
  ]
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-ink-950">
      {blobs.map((b, i) => (
        <div key={i} className="absolute rounded-full blur-[110px] will-change-transform"
             style={{
               width: b.size, height: b.size, top: b.top, left: b.left,
               background: `radial-gradient(circle at 30% 30%, ${b.c}, transparent 70%)`,
               animation: `aurora-drift ${b.dur} ease-in-out ${b.delay} infinite`,
             }} />
      ))}
      <div className="surface-grid absolute inset-0 opacity-70" />
      <div className="absolute inset-x-0 top-0 h-64 bg-gradient-to-b from-black/60 to-transparent" />
    </div>
  )
}
