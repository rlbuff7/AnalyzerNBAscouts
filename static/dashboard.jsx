// Dashboard variations — A: Terminal, B: Card grid, C: Editorial split

const { useState, useMemo, useEffect } = React;

// ---------- Helper: chave canônica de jogo a partir de uma prop ----------

function gameKey(prop) {
  const opp = (prop.game || "").replace(/^vs\s*/i, "").trim();
  const parts = [prop.team, opp].filter(Boolean).sort();
  return parts.length === 2 ? parts.join(" vs ") : "";
}

// ---------- Shared filter / metric utilities ----------

function applyFilters(props, { market, minEv, onlyStrong, game, search }) {
  const q = (search || "").trim().toLowerCase();
  return props.filter(p => {
    if (market !== "ALL" && p.market !== market) return false;
    if (p.ev_pct < minEv) return false;
    if (onlyStrong && p.rating !== "STRONG") return false;
    if (game && game !== "ALL" && gameKey(p) !== game) return false;
    if (q && !p.player_name.toLowerCase().includes(q)) return false;
    return true;
  });
}

function computeMetrics(props) {
  const total = props.length;
  const evPositive = props.filter(p => p.ev_pct > 0);
  const strong = props.filter(p => p.rating === "STRONG").length;
  const avgEv = evPositive.length
    ? evPositive.reduce((s, p) => s + p.ev_pct, 0) / evPositive.length
    : 0;
  return { total, evPositiveCount: evPositive.length, strong, avgEv };
}

// ---------- Filter Bar ----------

const DEFAULT_FILTERS = { market: "ALL", minEv: 3, onlyStrong: false, game: "ALL", search: "" };

function FilterBar({ filters, setFilters, games, onReset, density = "normal" }) {
  const { MARKETS } = window.NBA_DATA;
  const isFiltered = filters.market !== "ALL" || filters.minEv !== 3 || filters.onlyStrong
    || (filters.game && filters.game !== "ALL") || !!(filters.search || "");
  return (
    <div style={{
      display: "flex", flexDirection: "column", gap: 10,
      padding: density === "compact" ? "10px 14px" : "14px 18px",
      background: "#141419", border: "1px solid #2a2a38", borderRadius: 8,
      fontFamily: "'Inter Tight', sans-serif", fontSize: 13,
    }}>

      {/* Linha 1: busca + controles */}
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>

        {/* Busca por jogador */}
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          flex: "1 1 200px", minWidth: 0,
          padding: "5px 10px", borderRadius: 5,
          background: "#0f0f13", border: `1px solid ${(filters.search || "") ? "rgba(99,102,241,0.5)" : "#2a2a38"}`,
          transition: "border-color .15s",
        }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#5a5a72"
            strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
          </svg>
          <input
            type="text"
            placeholder="Buscar jogador…"
            value={filters.search || ""}
            onChange={e => setFilters({ ...filters, search: e.target.value })}
            style={{
              background: "transparent", border: "none", outline: "none",
              color: "#e8e8f0", fontSize: 13, fontFamily: "'Inter Tight', sans-serif",
              width: "100%", minWidth: 0,
            }}
          />
          {(filters.search || "") && (
            <button onClick={() => setFilters({ ...filters, search: "" })}
              style={{
                background: "none", border: "none", cursor: "pointer",
                color: "#5a5a72", padding: 0, fontSize: 17, lineHeight: 1, flexShrink: 0,
              }}>×</button>
          )}
        </div>

        <div style={{ width: 1, height: 20, background: "#2a2a38", flexShrink: 0 }} />

        {/* Mercado */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ color: "#5a5a72", fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.6 }}>MERCADO</span>
          <select value={filters.market} onChange={e => setFilters({ ...filters, market: e.target.value })}
            style={{
              background: "#0f0f13", color: "#e8e8f0", border: "1px solid #2a2a38",
              padding: "5px 10px", borderRadius: 5, fontFamily: "inherit", fontSize: 13, outline: "none",
            }}>
            {MARKETS.map(m => <option key={m.key} value={m.key}>{m.label}</option>)}
          </select>
        </div>

        {/* EV mín */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ color: "#5a5a72", fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.6 }}>EV MÍN.</span>
          <input type="range" min={0} max={20} step={0.5} value={filters.minEv}
            onChange={e => setFilters({ ...filters, minEv: +e.target.value })}
            style={{ width: 110, accentColor: "#6366f1" }} />
          <input
            type="number" min={0} max={20} step={0.5}
            value={filters.minEv}
            onChange={e => {
              const v = Math.max(0, Math.min(20, parseFloat(e.target.value) || 0));
              setFilters({ ...filters, minEv: v });
            }}
            style={{
              width: 52, background: "#0f0f13", border: "1px solid #2a2a38",
              color: "#e8e8f0", borderRadius: 4, padding: "4px 6px",
              fontFamily: "'JetBrains Mono', monospace", fontSize: 12,
              outline: "none", textAlign: "right",
            }}
          />
          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: "#5a5a72" }}>%</span>
        </div>

        {/* Só Strong */}
        <label style={{
          display: "flex", alignItems: "center", gap: 8, cursor: "pointer",
          padding: "5px 10px", borderRadius: 5,
          background: filters.onlyStrong ? "rgba(99,102,241,0.15)" : "transparent",
          border: `1px solid ${filters.onlyStrong ? "rgba(99,102,241,0.5)" : "#2a2a38"}`,
          color: filters.onlyStrong ? "#c7d2fe" : "#8888a0",
          fontSize: 12, fontWeight: 500, transition: "all .15s",
        }}>
          <input type="checkbox" checked={filters.onlyStrong}
            onChange={e => setFilters({ ...filters, onlyStrong: e.target.checked })}
            style={{ accentColor: "#6366f1", margin: 0 }} />
          Só Strong Bets
        </label>

        <div style={{ flex: 1 }} />

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: filters.resultCount === 0 ? "#fca5a5" : "#5a5a72" }}>
            {filters.resultCount} resultados
          </div>
          {isFiltered && (
            <button onClick={onReset} style={{
              padding: "4px 10px", borderRadius: 4,
              background: "transparent", border: "1px solid #3a3a4a",
              color: "#8888a0", cursor: "pointer",
              fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5,
              transition: "all .12s",
            }}
            onMouseEnter={e => { e.target.style.borderColor = "#6366f1"; e.target.style.color = "#c7d2fe"; }}
            onMouseLeave={e => { e.target.style.borderColor = "#3a3a4a"; e.target.style.color = "#8888a0"; }}>
              Limpar filtros
            </button>
          )}
        </div>
      </div>

      {/* Linha 2: filtro por jogo */}
      {games && games.length > 1 && (
        <div style={{
          display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6,
          paddingTop: 10, borderTop: "1px solid #2a2a38",
        }}>
          <span style={{
            color: "#5a5a72", fontFamily: "'JetBrains Mono', monospace",
            fontSize: 10, textTransform: "uppercase", letterSpacing: 0.6, marginRight: 2,
          }}>JOGO</span>
          {games.map(g => {
            const active = (filters.game || "ALL") === g.key;
            return (
              <button key={g.key} onClick={() => setFilters({ ...filters, game: g.key })}
                style={{
                  padding: "4px 12px", borderRadius: 20,
                  background: active ? "rgba(99,102,241,0.2)" : "transparent",
                  border: `1px solid ${active ? "rgba(99,102,241,0.55)" : "#2a2a38"}`,
                  color: active ? "#c7d2fe" : "#8888a0",
                  fontFamily: "'JetBrains Mono', monospace", fontSize: 11.5,
                  fontWeight: active ? 600 : 400,
                  cursor: "pointer", transition: "all .12s", whiteSpace: "nowrap",
                }}>
                {g.label}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------- Summary metric cards ----------

function MetricCard({ label, value, sub, color = "#e8e8f0", accent }) {
  return (
    <div style={{
      flex: 1, minWidth: 0,
      padding: "14px 18px",
      background: "#1a1a23", border: "1px solid #2a2a38", borderRadius: 8,
      position: "relative", overflow: "hidden",
    }}>
      {accent && (
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: accent }} />
      )}
      <div style={{
        fontFamily: "'JetBrains Mono', monospace", fontSize: 9.5, color: "#5a5a72",
        textTransform: "uppercase", letterSpacing: 1, marginBottom: 8,
      }}>{label}</div>
      <div style={{
        fontFamily: "'JetBrains Mono', monospace", fontSize: 26, fontWeight: 700, color, lineHeight: 1,
        letterSpacing: -0.5,
      }}>{value}</div>
      {sub && <div style={{ fontFamily: "'Inter Tight', sans-serif", fontSize: 11.5, color: "#5a5a72", marginTop: 6, letterSpacing: 0 }}>{sub}</div>}
    </div>
  );
}

function SummaryStrip({ metrics }) {
  return (
    <div style={{ display: "flex", gap: 12 }}>
      <MetricCard label="Props analisadas" value={metrics.total} sub="props no resultado filtrado" />
      <MetricCard label="EV Positivo" value={metrics.evPositiveCount}
        sub={`${metrics.total ? ((metrics.evPositiveCount / metrics.total) * 100).toFixed(0) : 0}% do total`}
        color="#4ade80" accent="#22c55e" />
      <MetricCard label="Strong Bets" value={metrics.strong}
        sub="EV ≥ 8% e prob ≥ 60%" color="#a5b4fc" accent="#6366f1" />
      <MetricCard label="EV médio (positivos)" value={`${metrics.avgEv.toFixed(1)}%`}
        sub="apenas props com EV > 0" color="#4ade80" accent="#22c55e" />
    </div>
  );
}

// ---------- Variation A — Trading Terminal table ----------

function PropsTableTerminal({ props, onPlayer, oddMode, navigate }) {
  const [sortBy, setSortBy] = useState("ev_pct");
  const [sortDir, setSortDir] = useState("desc");
  const [page, setPage] = useState(0);
  const PAGE = 12;

  const sorted = useMemo(() => {
    const arr = [...props].sort((a, b) => {
      const av = a[sortBy], bv = b[sortBy];
      if (typeof av === "string") return sortDir === "desc" ? bv.localeCompare(av) : av.localeCompare(bv);
      return sortDir === "desc" ? bv - av : av - bv;
    });
    return arr;
  }, [props, sortBy, sortDir]);

  useEffect(() => { setPage(0); }, [props]);

  const pageData = sorted.slice(page * PAGE, (page + 1) * PAGE);
  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE));

  const HEADER_TIPS = {
    "Prob Real": "Probabilidade verdadeira estimada de o evento acontecer, ponderando forma recente e média da temporada.",
    "EV%": "Expected Value: quanto acima do valor justo está a odd. Positivo = aposta com vantagem matemática.",
    "Kelly%": "Fração do bankroll sugerida pelo critério de Kelly. Indica convicção proporcional ao EV.",
    "Rating": "STRONG ≥ EV 8% e prob ≥ 60% · VALUE = EV positivo · NEUTRAL ≈ zero · AVOID = EV negativo.",
    "Odd": "Odd decimal. Implied prob = 1 / odd.",
    "Hit%": "% dos últimos jogos em que o jogador bateu essa linha. ≥60% verde · 40-60% amarelo · <40% vermelho.",
  };

  function header(label, key, align = "left") {
    const active = sortBy === key;
    const tip = HEADER_TIPS[label];
    return (
      <th onClick={() => {
        if (active) setSortDir(d => d === "desc" ? "asc" : "desc");
        else { setSortBy(key); setSortDir("desc"); }
      }}
        style={{
          textAlign: align, padding: "10px 12px",
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 10, fontWeight: 500, color: active ? "#a5b4fc" : "#5a5a72",
          textTransform: "uppercase", letterSpacing: 0.7, cursor: "pointer",
          borderBottom: "1px solid #2a2a38", whiteSpace: "nowrap", userSelect: "none",
        }}>
        {tip ? (
          <Tooltip text={tip}>
            <span>{label}{active ? (sortDir === "desc" ? " ↓" : " ↑") : ""}</span>
            <span style={{ marginLeft: 4, fontSize: 9, color: "#3a3a4a" }}>ⓘ</span>
          </Tooltip>
        ) : (
          <>{label}{active ? (sortDir === "desc" ? " ↓" : " ↑") : ""}</>
        )}
      </th>
    );
  }

  return (
    <div style={{
      background: "#141419", border: "1px solid #2a2a38", borderRadius: 8, overflow: "hidden",
    }}>
      <div style={{ overflowX: "auto", overflowY: "auto", maxHeight: 580 }}>
        <table style={{
          width: "100%", borderCollapse: "collapse",
          fontFamily: "'JetBrains Mono', monospace", fontSize: 12.5, color: "#e8e8f0",
        }}>
          <thead style={{ background: "#0f0f13", position: "sticky", top: 0, zIndex: 2 }}>
            <tr>
              {header("Jogador", "player_name")}
              {header("Jogo", "game")}
              {header("Mercado", "market")}
              {header("Linha", "line", "right")}
              {header("Dir", "direction")}
              {header("Odd", "odd", "right")}
              {header("Hit%", "games_over_line_pct", "right")}
              {header("Prob Real", "prob_real", "right")}
              {header("EV%", "ev_pct", "right")}
              {header("Kelly%", "kelly_pct", "right")}
              {header("Rating", "rating")}
              {header("Casa", "bookmaker")}
            </tr>
          </thead>
          <tbody>
            {pageData.map((p, i) => {
              const strong = p.rating === "STRONG";
              const rowBg = strong ? "rgba(99,102,241,0.05)" : (i % 2 ? "#141419" : "#161620");
              const evColor = p.ev_pct >= 8 ? "#4ade80" : p.ev_pct > 0 ? "#86efac" : p.ev_pct > -1 ? "#cbd5e1" : "#fca5a5";
              return (
                <tr key={i}
                  style={{ background: rowBg, borderBottom: "1px solid rgba(42,42,56,0.5)", transition: "background .12s" }}
                  onMouseEnter={e => e.currentTarget.style.background = "#1e1e28"}
                  onMouseLeave={e => e.currentTarget.style.background = rowBg}>
                  <td style={{ padding: "10px 12px", whiteSpace: "nowrap" }}>
                    <StarButton prop={p} style={{ marginRight: 4 }} />
                    <a onClick={() => onPlayer(p.player_name)}
                      style={{
                        color: "#c7d2fe", cursor: "pointer", textDecoration: "none",
                        fontFamily: "'Inter Tight', sans-serif", fontWeight: 500,
                      }}
                      onMouseEnter={e => e.target.style.color = "#a5b4fc"}
                      onMouseLeave={e => e.target.style.color = "#c7d2fe"}>
                      {p.player_name}
                    </a>
                    <span style={{ color: "#5a5a72", marginLeft: 8, fontSize: 10.5 }}>{p.team}</span>
                    <InjuryAlert injuries={p.team_injuries} />
                  </td>
                  <td style={{ padding: "10px 12px", color: "#8888a0" }}>{p.game}</td>
                  <td style={{ padding: "10px 12px", color: "#cbd5e1" }}>{p.market}</td>
                  <td style={{ padding: "10px 12px", textAlign: "right", whiteSpace: "nowrap" }}>
                    {p.line}
                    {p.line_movement != null && Math.abs(p.line_movement) >= 0.5 && (
                      <Tooltip text={`Abriu em ${p.line_opened} · movimento ${p.line_movement > 0 ? "+" : ""}${p.line_movement}`}>
                        <span style={{
                          marginLeft: 5, fontSize: 11,
                          color: p.line_movement > 0 ? "#4ade80" : "#fca5a5",
                        }}>{p.line_movement > 0 ? "⬆" : "⬇"}</span>
                      </Tooltip>
                    )}
                  </td>
                  <td style={{ padding: "10px 12px", color: p.direction === "OVER" ? "#86efac" : "#fca5a5" }}>
                    {p.direction === "OVER" ? "▲ O" : "▼ U"}
                  </td>
                  <td style={{ padding: "10px 12px", textAlign: "right" }}>{fmtOdd(p.odd, oddMode)}</td>
                  <td style={{ padding: "10px 12px", textAlign: "right" }}>
                    {p.games_over_line_pct != null ? (() => {
                      const pct = p.games_over_line_pct;
                      const color = pct >= 0.6 ? "#4ade80" : pct >= 0.4 ? "#fde047" : "#fca5a5";
                      return <span style={{ color, fontWeight: 600 }}>{(pct * 100).toFixed(0)}%</span>;
                    })() : "—"}
                  </td>
                  <td style={{ padding: "10px 12px", textAlign: "right", color: "#cbd5e1" }}>{fmtProb(p.prob_real)}</td>
                  <td style={{ padding: "10px 12px", textAlign: "right", color: evColor, fontWeight: 600 }}>
                    {fmtPct(p.ev_pct)}
                  </td>
                  <td style={{ padding: "10px 12px", textAlign: "right", color: p.kelly_pct > 0 ? "#a5b4fc" : "#5a5a72" }}>
                    {p.kelly_pct.toFixed(1)}%
                  </td>
                  <td style={{ padding: "10px 12px" }}>
                    <RatingBadge rating={p.rating} />
                  </td>
                  <td style={{ padding: "10px 12px", color: "#8888a0", fontSize: 11 }}>
                    <OddsShoppingBadge bookmaker={p.bookmaker} allOdds={p.all_odds} />
                  </td>
                </tr>
              );
            })}
            {pageData.length === 0 && (
              <tr><td colSpan={12} style={{ padding: 40, textAlign: "center", color: "#5a5a72" }}>
                Nenhuma prop bate seus filtros.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {pageCount > 1 && (
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "10px 14px", borderTop: "1px solid #2a2a38",
          fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#8888a0",
        }}>
          <span>Página {page + 1} de {pageCount} · {sorted.length} props</span>
          <div style={{ display: "flex", gap: 6 }}>
            <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
              style={pageBtnStyle(page === 0)}>← Anterior</button>
            <button onClick={() => setPage(p => Math.min(pageCount - 1, p + 1))} disabled={page >= pageCount - 1}
              style={pageBtnStyle(page >= pageCount - 1)}>Próxima →</button>
          </div>
        </div>
      )}
    </div>
  );
}

function pageBtnStyle(disabled) {
  return {
    padding: "5px 12px",
    background: disabled ? "transparent" : "#1a1a23",
    border: "1px solid #2a2a38", borderRadius: 4,
    color: disabled ? "#3a3a4a" : "#cbd5e1",
    fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
    cursor: disabled ? "default" : "pointer",
  };
}

// ---------- Variation B — Card grid ----------

function PropsCards({ props, onPlayer, oddMode }) {
  const [page, setPage] = useState(0);
  const PAGE = 12;

  useEffect(() => { setPage(0); }, [props]);

  const sorted = [...props].sort((a, b) => b.ev_pct - a.ev_pct);
  const pageData = sorted.slice(page * PAGE, (page + 1) * PAGE);
  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE));

  return (
    <div>
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12,
      }}>
        {pageData.map((p, i) => <PropCard key={i} prop={p} onPlayer={onPlayer} oddMode={oddMode} />)}
        {pageData.length === 0 && (
          <div style={{
            gridColumn: "1 / -1", padding: 60, textAlign: "center",
            color: "#5a5a72", fontFamily: "'Inter Tight', sans-serif",
            background: "#141419", border: "1px dashed #2a2a38", borderRadius: 8,
          }}>Nenhuma prop bate seus filtros.</div>
        )}
      </div>
      {pageCount > 1 && (
        <div style={{
          marginTop: 16, display: "flex", justifyContent: "space-between", alignItems: "center",
          fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#8888a0",
        }}>
          <span>Página {page + 1} de {pageCount} · {sorted.length} props</span>
          <div style={{ display: "flex", gap: 6 }}>
            <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0} style={pageBtnStyle(page === 0)}>← Anterior</button>
            <button onClick={() => setPage(p => Math.min(pageCount - 1, p + 1))} disabled={page >= pageCount - 1} style={pageBtnStyle(page >= pageCount - 1)}>Próxima →</button>
          </div>
        </div>
      )}
    </div>
  );
}

function PropCard({ prop, onPlayer, oddMode }) {
  const t = RATING_TOKENS[prop.rating];
  const evColor = prop.ev_pct >= 8 ? "#4ade80" : prop.ev_pct > 0 ? "#86efac" : prop.ev_pct > -1 ? "#cbd5e1" : "#fca5a5";
  const isStrong = prop.rating === "STRONG";
  const [hovered, setHovered] = React.useState(false);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: isStrong
          ? "linear-gradient(180deg, #1c1c2a 0%, #161620 100%)"
          : "#1a1a23",
        border: `1px solid ${isStrong
          ? (hovered ? "rgba(99,102,241,0.6)" : "rgba(99,102,241,0.4)")
          : (hovered ? "#3a3a4a" : "#2a2a38")}`,
        borderRadius: 10, padding: 14, position: "relative", overflow: "hidden",
        transition: "border-color .15s, box-shadow .15s",
        boxShadow: isStrong && hovered ? "0 4px 24px rgba(99,102,241,0.12)" : "none",
      }}>
      {/* Accent bar left */}
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: t.dot, borderRadius: "0 0 0 0" }} />
      {/* Strong glow top-right */}
      {isStrong && (
        <div style={{
          position: "absolute", top: 0, right: 0, width: 80, height: 80,
          background: "radial-gradient(circle, rgba(99,102,241,0.14), transparent 70%)",
          pointerEvents: "none",
        }} />
      )}

      {/* Header: nome + badge */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 10, marginBottom: 10 }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <a onClick={() => onPlayer(prop.player_name)}
            style={{
              color: "#e8e8f0", cursor: "pointer", fontFamily: "'Inter Tight', sans-serif",
              fontWeight: 600, fontSize: 14.5, display: "block", lineHeight: 1.2,
              whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
              transition: "color .12s",
            }}
            onMouseEnter={e => e.target.style.color = "#a5b4fc"}
            onMouseLeave={e => e.target.style.color = "#e8e8f0"}
          >{prop.player_name}</a>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#8888a0", marginTop: 3, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {prop.team} · {prop.game}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
          <StarButton prop={prop} />
          <RatingBadge rating={prop.rating} />
        </div>
      </div>

      {/* Linha / mercado */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "9px 11px", background: "#0f0f13", borderRadius: 6, marginBottom: 10,
        fontFamily: "'JetBrains Mono', monospace",
        border: "1px solid rgba(42,42,56,0.6)",
      }}>
        <span style={{
          padding: "2px 7px", borderRadius: 3,
          background: "rgba(90,90,114,0.15)", border: "1px solid rgba(90,90,114,0.25)",
          fontSize: 9.5, color: "#5a5a72", textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 600,
        }}>{prop.market}</span>
        <span style={{ color: prop.direction === "OVER" ? "#86efac" : "#fca5a5", fontSize: 12, fontWeight: 700, letterSpacing: 0.3 }}>
          {prop.direction === "OVER" ? "OVER" : "UNDER"}
        </span>
        <span style={{ color: "#e8e8f0", fontSize: 20, fontWeight: 700, letterSpacing: -0.5 }}>{prop.line}</span>
        {prop.line_movement != null && Math.abs(prop.line_movement) >= 0.5 && (
          <Tooltip text={`Abriu em ${prop.line_opened} · movimento ${prop.line_movement > 0 ? "+" : ""}${prop.line_movement}`}>
            <span style={{ fontSize: 12, color: prop.line_movement > 0 ? "#4ade80" : "#fca5a5" }}>
              {prop.line_movement > 0 ? "⬆" : "⬇"}
            </span>
          </Tooltip>
        )}
        <span style={{ flex: 1 }} />
        <span style={{ color: "#a0a0c0", fontSize: 12, fontWeight: 500 }}>{fmtOdd(prop.odd, oddMode)}</span>
      </div>

      {/* Stats grid */}
      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 1, background: "#2a2a38",
        border: "1px solid #2a2a38", borderRadius: 6, overflow: "hidden",
      }}>
        <Stat label="EV%" value={fmtPct(prop.ev_pct)} color={evColor}
          tip="Expected Value: quanto acima do valor justo está a odd. Positivo = vantagem matemática." />
        <Stat label="Prob Real" value={fmtProb(prop.prob_real)} color="#cbd5e1"
          tip="Probabilidade real estimada com base na forma recente + média da temporada." />
        <Stat label="Kelly" value={`${prop.kelly_pct.toFixed(1)}%`} color={prop.kelly_pct > 0 ? "#a5b4fc" : "#5a5a72"}
          tip="Fração de bankroll sugerida pelo critério de Kelly. Use apenas como referência." />
      </div>

      {/* Hit rate bar se disponível */}
      {prop.games_over_line_pct != null && (() => {
        const pct = prop.games_over_line_pct;
        const color = pct >= 0.6 ? "#4ade80" : pct >= 0.4 ? "#fde047" : "#fca5a5";
        return (
          <div style={{ marginTop: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3, fontFamily: "'JetBrains Mono', monospace", fontSize: 9.5, color: "#5a5a72" }}>
              <span>Hit rate · últimos jogos</span>
              <span style={{ color, fontWeight: 600 }}>{(pct * 100).toFixed(0)}%</span>
            </div>
            <div style={{ height: 3, background: "#2a2a38", borderRadius: 2, overflow: "hidden" }}>
              <div style={{ width: `${pct * 100}%`, height: "100%", background: color, borderRadius: 2, transition: "width .4s" }} />
            </div>
          </div>
        );
      })()}

      <div style={{ marginTop: 10, fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5, color: "#5a5a72" }}>
        <OddsShoppingBadge bookmaker={prop.bookmaker} allOdds={prop.all_odds} />
      </div>
    </div>
  );
}

function InjuryAlert({ injuries }) {
  if (!injuries || !injuries.length) return null;
  const relevant = injuries.filter(i =>
    ["out", "questionable"].includes((i.status || "").toLowerCase())
  );
  if (!relevant.length) return null;
  const tipText = relevant.map(i => `${i.name}: ${i.status}`).join(" · ");
  return (
    <Tooltip text={tipText}>
      <span style={{ marginLeft: 6, fontSize: 12, cursor: "default" }} title={tipText}>⚠</span>
    </Tooltip>
  );
}

function OddsShoppingBadge({ bookmaker, allOdds }) {
  const extras = (allOdds || []).filter(o => o.bookmaker !== bookmaker);
  if (!extras.length) {
    return <span>{bookmaker}</span>;
  }
  const tipText = [
    `Melhor: ${bookmaker}`,
    ...extras.map(o => `${o.bookmaker}: ${o.odd.toFixed(2)}`),
  ].join(" · ");
  return (
    <Tooltip text={tipText}>
      <span style={{ borderBottom: "1px dashed #3a3a4a", cursor: "default" }}>{bookmaker}</span>
      <span style={{ marginLeft: 5, padding: "1px 5px", borderRadius: 3, fontSize: 9.5, fontWeight: 600, color: "#a5b4fc", background: "rgba(99,102,241,0.12)", border: "1px solid rgba(99,102,241,0.25)" }}>
        +{extras.length}
      </span>
    </Tooltip>
  );
}

function Stat({ label, value, color, tip }) {
  return (
    <div style={{ background: "#141419", padding: "8px 10px" }}>
      <div style={{
        fontFamily: "'JetBrains Mono', monospace", fontSize: 9.5, color: "#5a5a72",
        textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 3,
      }}>
        {tip ? (
          <Tooltip text={tip}>
            <span>{label}</span>
            <span style={{ marginLeft: 3, fontSize: 8, color: "#3a3a4a" }}>ⓘ</span>
          </Tooltip>
        ) : label}
      </div>
      <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 13, fontWeight: 600, color }}>{value}</div>
    </div>
  );
}

// ---------- Variation C — Editorial split ----------

function PropsEditorial({ props, onPlayer, oddMode }) {
  const sorted = [...props].sort((a, b) => b.ev_pct - a.ev_pct);
  const featured = sorted.filter(p => p.rating === "STRONG").slice(0, 3);
  const rest = sorted.filter(p => !featured.includes(p));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr)", gap: 18 }}>
      {featured.length > 0 && (
        <div>
          <SectionLabel>Strong Bets em destaque</SectionLabel>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
            {featured.map((p, i) => <FeaturedCard key={i} prop={p} onPlayer={onPlayer} oddMode={oddMode} />)}
          </div>
        </div>
      )}
      <div>
        <SectionLabel>Demais oportunidades</SectionLabel>
        <PropsTableTerminal props={rest} onPlayer={onPlayer} oddMode={oddMode} />
      </div>
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12, marginBottom: 10,
      fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5, color: "#5a5a72",
      textTransform: "uppercase", letterSpacing: 1,
    }}>
      <span>{children}</span>
      <span style={{ flex: 1, height: 1, background: "#2a2a38" }} />
    </div>
  );
}

function FeaturedCard({ prop, onPlayer, oddMode }) {
  const evColor = prop.ev_pct >= 8 ? "#4ade80" : prop.ev_pct > 0 ? "#86efac" : "#cbd5e1";
  return (
    <div style={{
      background: "linear-gradient(180deg, #1a1a28 0%, #15151d 100%)",
      border: "1px solid rgba(99,102,241,0.35)",
      borderRadius: 12, padding: 20, position: "relative", overflow: "hidden",
      transition: "border-color .15s, box-shadow .15s",
    }}
    onMouseEnter={e => { e.currentTarget.style.borderColor = "rgba(99,102,241,0.6)"; e.currentTarget.style.boxShadow = "0 4px 28px rgba(99,102,241,0.15)"; }}
    onMouseLeave={e => { e.currentTarget.style.borderColor = "rgba(99,102,241,0.35)"; e.currentTarget.style.boxShadow = "none"; }}>
      {/* Glow top-right */}
      <div style={{
        position: "absolute", top: 0, right: 0, width: 140, height: 140,
        background: "radial-gradient(circle, rgba(99,102,241,0.2), transparent 70%)",
        pointerEvents: "none",
      }} />
      {/* Accent bar left */}
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: "rgba(99,102,241,0.8)" }} />

      <div style={{ position: "relative" }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14, gap: 12 }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <a onClick={() => onPlayer(prop.player_name)}
              style={{
                color: "#e8e8f0", cursor: "pointer", fontFamily: "'Inter Tight', sans-serif",
                fontWeight: 700, fontSize: 20, display: "block", lineHeight: 1.1,
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                transition: "color .12s",
              }}
              onMouseEnter={e => e.target.style.color = "#a5b4fc"}
              onMouseLeave={e => e.target.style.color = "#e8e8f0"}
            >{prop.player_name}</a>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#8888a0", marginTop: 5, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {prop.team} · {prop.game}
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            <StarButton prop={prop} />
            <RatingBadge rating={prop.rating} size="md" />
          </div>
        </div>

        {/* Linha principal */}
        <div style={{
          fontFamily: "'JetBrains Mono', monospace",
          display: "flex", alignItems: "center", gap: 10, marginBottom: 18,
          padding: "10px 12px", background: "rgba(15,15,19,0.8)", borderRadius: 7,
          border: "1px solid rgba(42,42,56,0.6)",
        }}>
          <span style={{ fontSize: 10.5, color: "#5a5a72", textTransform: "uppercase", letterSpacing: 0.6 }}>{prop.market}</span>
          <span style={{ color: prop.direction === "OVER" ? "#86efac" : "#fca5a5", fontSize: 13, fontWeight: 700 }}>
            {prop.direction}
          </span>
          <span style={{ fontSize: 30, color: "#e8e8f0", fontWeight: 700, letterSpacing: -1 }}>{prop.line}</span>
          {prop.line_movement != null && Math.abs(prop.line_movement) >= 0.5 && (
            <Tooltip text={`Abriu em ${prop.line_opened} · movimento ${prop.line_movement > 0 ? "+" : ""}${prop.line_movement}`}>
              <span style={{ fontSize: 13, color: prop.line_movement > 0 ? "#4ade80" : "#fca5a5" }}>
                {prop.line_movement > 0 ? "⬆" : "⬇"}
              </span>
            </Tooltip>
          )}
          <span style={{ flex: 1 }} />
          <span style={{ color: "#5a5a72", fontSize: 11 }}>@</span>
          <span style={{ color: "#a0a0c0", fontSize: 16, fontWeight: 600 }}>{fmtOdd(prop.odd, oddMode)}</span>
        </div>

        {/* Stats + hit rate */}
        <div style={{ display: "flex", gap: 22, fontFamily: "'JetBrains Mono', monospace", marginBottom: 12 }}>
          <BigStat label="EV%" value={fmtPct(prop.ev_pct)} color={evColor} />
          <BigStat label="Prob Real" value={fmtProb(prop.prob_real)} color="#cbd5e1" />
          <BigStat label="Kelly" value={`${prop.kelly_pct.toFixed(1)}%`} color="#a5b4fc" />
          {prop.games_over_line_pct != null && (() => {
            const pct = prop.games_over_line_pct;
            const color = pct >= 0.6 ? "#4ade80" : pct >= 0.4 ? "#fde047" : "#fca5a5";
            return <BigStat label="Hit%" value={`${(pct * 100).toFixed(0)}%`} color={color} />;
          })()}
        </div>

        {/* Bookmaker */}
        <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5, color: "#5a5a72" }}>
          <OddsShoppingBadge bookmaker={prop.bookmaker} allOdds={prop.all_odds} />
        </div>
      </div>
    </div>
  );
}

function BigStat({ label, value, color }) {
  return (
    <div>
      <div style={{ fontSize: 9.5, color: "#5a5a72", textTransform: "uppercase", letterSpacing: 0.7, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 17, fontWeight: 600, color }}>{value}</div>
    </div>
  );
}

// ---------- Dashboard root ----------

function Dashboard({ navigate, tweaks, setTweak }) {
  const { PROPS, GENERATED_AT, QUOTA_LIMIT, FROM_CACHE, DEMO_MODE } = window.NBA_DATA;
  const [favCount, setFavCount] = useState(() => window.NBA_FAVORITES.count());
  const [showFavOnly, setShowFavOnly] = useState(false);

  useEffect(() => {
    const onUpdate = () => setFavCount(window.NBA_FAVORITES.count());
    window.addEventListener("nba-favorites-changed", onUpdate);
    return () => window.removeEventListener("nba-favorites-changed", onUpdate);
  }, []);

  const [filters, setFilters] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem("nba-scout-filters") || "null");
      if (saved) return { game: "ALL", search: "", ...saved };
    } catch (e) {}
    return { market: "ALL", minEv: 3, onlyStrong: false, game: "ALL", search: "" };
  });

  useEffect(() => {
    localStorage.setItem("nba-scout-filters", JSON.stringify(filters));
  }, [filters]);

  // Extrai jogos únicos do dia para os pills de filtro
  const games = useMemo(() => {
    const seen = new Set();
    const list = [{ key: "ALL", label: "Todos os jogos" }];
    for (const p of PROPS) {
      const k = gameKey(p);
      if (k && !seen.has(k)) {
        seen.add(k);
        list.push({ key: k, label: k });
      }
    }
    return list;
  }, [PROPS]);

  const filtered = useMemo(() => {
    const base = showFavOnly
      ? PROPS.filter(p => window.NBA_FAVORITES.has(p))
      : PROPS;
    return applyFilters(base, filters);
  }, [PROPS, filters, showFavOnly, favCount]);
  const metrics = useMemo(() => computeMetrics(filtered), [filtered]);

  const generatedAt = new Date(GENERATED_AT);
  const fromCache = FROM_CACHE;
  const used = QUOTA_LIMIT - window.NBA_DATA.QUOTA_REMAINING;
  const variation = tweaks.variation;

  return (
    <div style={{
      minHeight: "100vh", background: "#0f0f13", color: "#e8e8f0",
      fontFamily: "'Inter Tight', sans-serif",
    }}>
      <header style={{
        position: "sticky", top: 0, zIndex: 10,
        background: "rgba(15,15,19,0.92)", backdropFilter: "blur(8px)",
        borderBottom: "1px solid #2a2a38",
      }}>
        <div style={{
          maxWidth: 1480, margin: "0 auto", padding: "14px 28px",
          display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
            <div style={{
              width: 28, height: 28, borderRadius: 6, flexShrink: 0,
              background: "linear-gradient(135deg, #6366f1, #4f46e5)",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, fontSize: 13, color: "#fff",
            }}>NS</div>
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 16, lineHeight: 1, letterSpacing: -0.2, whiteSpace: "nowrap" }}>
                NBA Scout
              </div>
              <div style={{
                fontFamily: "'JetBrains Mono', monospace", fontSize: 9.5,
                color: "#5a5a72", textTransform: "uppercase", letterSpacing: 1, marginTop: 2, whiteSpace: "nowrap",
              }}>EV Analyzer</div>
            </div>
          </div>

          <div style={{
            fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#5a5a72",
            paddingLeft: 16, marginLeft: 4, borderLeft: "1px solid #2a2a38",
            display: "flex", alignItems: "center", gap: 8, whiteSpace: "nowrap", flexShrink: 0,
          }}>
            <span style={{
              display: "inline-block", width: 6, height: 6, borderRadius: "50%",
              background: "#22c55e", boxShadow: "0 0 6px #22c55e",
            }} />
            {new Date().toLocaleDateString("pt-BR")} · {filtered.length} props
          </div>

          <div style={{ flex: 1 }} />

          {DEMO_MODE && (
            <div style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              padding: "5px 10px", borderRadius: 6, flexShrink: 0, whiteSpace: "nowrap",
              background: "rgba(139,92,246,0.12)", border: "1px solid rgba(139,92,246,0.4)",
              fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#c4b5fd",
              fontWeight: 600, letterSpacing: "0.04em",
            }}>
              ⚡ DEMO · odds sintéticas
            </div>
          )}

          {fromCache && !DEMO_MODE && (
            <div style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "6px 10px", borderRadius: 6, flexShrink: 0, whiteSpace: "nowrap",
              background: "rgba(234,179,8,0.08)", border: "1px solid rgba(234,179,8,0.25)",
              fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#fde047",
            }}>
              <span style={{ width: 5, height: 5, borderRadius: "50%", background: "#eab308" }} />
              Do cache · {generatedAt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
            </div>
          )}

          <QuotaBadge used={used} limit={QUOTA_LIMIT} />

          <button style={{
            display: "inline-flex", alignItems: "center", gap: 8, flexShrink: 0, whiteSpace: "nowrap",
            padding: "7px 14px", borderRadius: 6,
            background: "#6366f1", border: "1px solid #4f46e5", color: "#fff",
            fontFamily: "'Inter Tight', sans-serif", fontSize: 13, fontWeight: 600, cursor: "pointer",
          }}
          onClick={() => window.location.reload()}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 12a9 9 0 0 1-9 9c-2.4 0-4.6-.94-6.2-2.5" />
              <path d="M3 12a9 9 0 0 1 9-9c2.4 0 4.6.94 6.2 2.5" />
              <path d="M21 5v4h-4M3 19v-4h4" />
            </svg>
            Atualizar
          </button>
        </div>

        {/* Abas de variação */}
        <div style={{
          maxWidth: 1480, margin: "0 auto", padding: "0 28px",
          display: "flex", gap: 4, borderTop: "1px solid #2a2a38",
        }}>
          {[
            { k: "terminal", label: "Terminal", desc: "denso · tabela" },
            { k: "cards", label: "Card grid", desc: "respiração · cards" },
            { k: "editorial", label: "Editorial", desc: "destaques · split" },
          ].map(v => (
            <button key={v.k} onClick={() => { setTweak("variation", v.k); setShowFavOnly(false); }}
              style={{
                background: "transparent", border: "none", cursor: "pointer",
                padding: "10px 14px", color: (variation === v.k && !showFavOnly) ? "#e8e8f0" : "#5a5a72",
                borderBottom: `2px solid ${(variation === v.k && !showFavOnly) ? "#6366f1" : "transparent"}`,
                fontFamily: "'Inter Tight', sans-serif", fontSize: 13, fontWeight: 500,
                display: "flex", alignItems: "baseline", gap: 8, transition: "color .12s",
              }}>
              {v.label}
              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: "#5a5a72" }}>{v.desc}</span>
            </button>
          ))}
          <button onClick={() => setShowFavOnly(f => !f)}
            style={{
              background: "transparent", border: "none", cursor: "pointer",
              padding: "10px 14px", color: showFavOnly ? "#fde047" : "#5a5a72",
              borderBottom: `2px solid ${showFavOnly ? "#fde047" : "transparent"}`,
              fontFamily: "'Inter Tight', sans-serif", fontSize: 13, fontWeight: 500,
              display: "flex", alignItems: "baseline", gap: 8, transition: "color .12s",
            }}>
            ★ Favoritos
            {favCount > 0 && (
              <span style={{
                marginLeft: 4, padding: "1px 6px", borderRadius: 10,
                background: showFavOnly ? "rgba(253,224,71,0.2)" : "rgba(253,224,71,0.1)",
                border: "1px solid rgba(253,224,71,0.3)",
                fontFamily: "'JetBrains Mono', monospace", fontSize: 10,
                color: "#fde047", fontWeight: 600,
              }}>{favCount}</span>
            )}
          </button>
        </div>
      </header>

      <main style={{ maxWidth: 1480, margin: "0 auto", padding: "20px 28px 80px", display: "flex", flexDirection: "column", gap: 16 }}>
        <SummaryStrip metrics={metrics} />
        <FilterBar
          filters={{ ...filters, resultCount: filtered.length }}
          setFilters={setFilters}
          games={games}
          onReset={() => setFilters(DEFAULT_FILTERS)}
        />

        {variation === "terminal" && <PropsTableTerminal props={filtered} onPlayer={n => navigate(`player/${n}`)} oddMode={tweaks.oddMode} />}
        {variation === "cards" && <PropsCards props={filtered} onPlayer={n => navigate(`player/${n}`)} oddMode={tweaks.oddMode} />}
        {variation === "editorial" && <PropsEditorial props={filtered} onPlayer={n => navigate(`player/${n}`)} oddMode={tweaks.oddMode} />}
      </main>
    </div>
  );
}

Object.assign(window, { Dashboard });
