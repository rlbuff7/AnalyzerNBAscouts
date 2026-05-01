// Shared atoms used across the app

const RATING_TOKENS = {
  STRONG: { fg: "#4ade80", bg: "rgba(34,197,94,0.14)", border: "rgba(34,197,94,0.35)", dot: "#22c55e" },
  VALUE:  { fg: "#93c5fd", bg: "rgba(59,130,246,0.14)", border: "rgba(59,130,246,0.35)", dot: "#3b82f6" },
  NEUTRAL:{ fg: "#cbd5e1", bg: "rgba(120,130,150,0.12)", border: "rgba(120,130,150,0.28)", dot: "#8888a0" },
  AVOID:  { fg: "#fca5a5", bg: "rgba(239,68,68,0.14)", border: "rgba(239,68,68,0.35)", dot: "#ef4444" },
};

function RatingBadge({ rating, size = "sm" }) {
  const t = RATING_TOKENS[rating] || RATING_TOKENS.NEUTRAL;
  const padY = size === "sm" ? 2 : 4;
  const padX = size === "sm" ? 7 : 10;
  const fs = size === "sm" ? 10.5 : 12;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      padding: `${padY}px ${padX}px`,
      borderRadius: 4,
      fontFamily: "'JetBrains Mono', monospace",
      fontSize: fs, fontWeight: 600, letterSpacing: 0.4,
      color: t.fg, background: t.bg, border: `1px solid ${t.border}`,
      lineHeight: 1, textTransform: "uppercase",
    }}>
      <span style={{ width: 5, height: 5, borderRadius: 1, background: t.dot }} />
      {rating}
    </span>
  );
}

function QuotaBadge({ used, limit }) {
  const remaining = limit - used;
  const pct = remaining / limit;
  let color = "#22c55e";
  if (remaining <= 30) color = "#ef4444";
  else if (remaining <= 100) color = "#eab308";
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: 10,
      padding: "6px 10px",
      borderRadius: 6, flexShrink: 0, whiteSpace: "nowrap",
      background: "#1a1a23",
      border: "1px solid #2a2a38",
      fontFamily: "'JetBrains Mono', monospace",
      fontSize: 11.5,
      color: "#8888a0",
    }}>
      <span style={{ color: "#5a5a72", textTransform: "uppercase", letterSpacing: 0.6, fontSize: 10 }}>QUOTA</span>
      <span style={{
        width: 60, height: 4, borderRadius: 2, background: "#0f0f13", overflow: "hidden", position: "relative",
      }}>
        <span style={{
          position: "absolute", inset: 0, width: `${pct * 100}%`, background: color,
        }} />
      </span>
      <span style={{ color: "#e8e8f0", fontWeight: 600 }}>{remaining}</span>
      <span style={{ color: "#5a5a72" }}>/ {limit}</span>
    </div>
  );
}

function Sparkline({ data, color = "#6366f1", w = 80, h = 22, line = null }) {
  if (!data?.length) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const stepX = w / (data.length - 1);
  const pts = data.map((v, i) => {
    const x = i * stepX;
    const y = h - ((v - min) / span) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const path = "M " + pts.join(" L ");
  // baseline area
  const area = `M 0,${h} L ` + pts.join(" L ") + ` L ${w},${h} Z`;
  let lineY = null;
  if (line != null) {
    lineY = h - ((line - min) / span) * h;
  }
  return (
    <svg width={w} height={h} style={{ display: "block", overflow: "visible" }}>
      <path d={area} fill={color} fillOpacity={0.12} />
      <path d={path} fill="none" stroke={color} strokeWidth={1.4} strokeLinejoin="round" strokeLinecap="round" />
      {lineY != null && (
        <line x1={0} x2={w} y1={lineY} y2={lineY}
          stroke="#5a5a72" strokeDasharray="2 3" strokeWidth={0.8} />
      )}
      <circle cx={(data.length - 1) * stepX} cy={h - ((data[data.length - 1] - min) / span) * h}
        r={1.6} fill={color} />
    </svg>
  );
}

function MicroBar({ value, max, color = "#6366f1", w = 56, h = 4 }) {
  const pct = Math.max(0, Math.min(1, value / max));
  return (
    <span style={{
      display: "inline-block", width: w, height: h, borderRadius: 2,
      background: "#0f0f13", position: "relative", verticalAlign: "middle",
    }}>
      <span style={{
        position: "absolute", inset: 0, width: `${pct * 100}%`, background: color, borderRadius: 2,
      }} />
    </span>
  );
}

const SHIMMER_STYLE = (() => {
  if (!document.getElementById("nba-shimmer-style")) {
    const s = document.createElement("style");
    s.id = "nba-shimmer-style";
    s.textContent = `
      @keyframes nba-shimmer {
        0%   { background-position: -400px 0; }
        100% { background-position:  400px 0; }
      }
      .nba-skeleton {
        background: linear-gradient(90deg, #1a1a23 25%, #2a2a38 50%, #1a1a23 75%);
        background-size: 800px 100%;
        animation: nba-shimmer 1.4s infinite linear;
        border-radius: 4px;
      }
    `;
    document.head.appendChild(s);
  }
  return null;
})();

function SkeletonBlock({ w = "100%", h = 16, style = {} }) {
  SHIMMER_STYLE;
  return (
    <span className="nba-skeleton" style={{ display: "block", width: w, height: h, ...style }} />
  );
}

function Tooltip({ text, children }) {
  const [show, setShow] = React.useState(false);
  return (
    <span style={{ position: "relative", display: "inline-flex", alignItems: "center" }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <span style={{
          position: "absolute", bottom: "calc(100% + 6px)", left: "50%",
          transform: "translateX(-50%)",
          background: "#1e1e28", border: "1px solid #3a3a4a",
          color: "#cbd5e1", fontSize: 11.5,
          fontFamily: "'Inter Tight', sans-serif",
          fontWeight: 400, letterSpacing: 0,
          padding: "6px 10px", borderRadius: 5,
          whiteSpace: "nowrap", maxWidth: 280, lineHeight: 1.5,
          boxShadow: "0 4px 16px rgba(0,0,0,0.5)",
          zIndex: 100, pointerEvents: "none",
          textTransform: "none",
        }}>{text}</span>
      )}
    </span>
  );
}

// number / odds formatting
function fmtOdd(o, mode) {
  if (mode === "implied") return `${(100 / o).toFixed(1)}%`;
  return o.toFixed(2);
}
function fmtPct(v, digits = 1) {
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(digits)}%`;
}
function fmtProb(p) { return `${(p * 100).toFixed(1)}%`; }

Object.assign(window, {
  RATING_TOKENS, RatingBadge, QuotaBadge, Sparkline, MicroBar, Tooltip, SkeletonBlock,
  fmtOdd, fmtPct, fmtProb,
});
