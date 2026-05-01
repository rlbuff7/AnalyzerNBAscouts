// Player detail page — busca dados reais de /api/player/{name}

function getStatValue(g, market) {
  switch (market) {
    case "PTS":    return g.pts;
    case "REB":    return g.reb;
    case "AST":    return g.ast;
    case "FG3M":   return g.fg3m;
    case "BLK":    return g.blk;
    case "STL":    return g.stl;
    case "PRA":    return g.pts + g.reb + g.ast;
    case "PR":     return g.pts + g.reb;
    case "PA":     return g.pts + g.ast;
    case "RA":     return g.reb + g.ast;
    case "STOCKS": return g.blk + g.stl;
    default:       return null;
  }
}

function HitRateBar({ hit, total, line, direction }) {
  if (!total) return null;
  const pct = hit / total;
  const color = pct >= 0.6 ? "#4ade80" : pct >= 0.4 ? "#fde047" : "#fca5a5";
  return (
    <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid #2a2a38" }}>
      <div style={{
        display: "flex", justifyContent: "space-between", marginBottom: 5,
        fontFamily: "'JetBrains Mono', monospace", fontSize: 10,
      }}>
        <span style={{ color: "#5a5a72" }}>
          {direction === "OVER" ? "OVER" : "UNDER"} {line} · últimos {total} jogos
        </span>
        <span style={{ color, fontWeight: 600 }}>{hit}/{total} · {(pct * 100).toFixed(0)}%</span>
      </div>
      <div style={{ height: 3, background: "#2a2a38", borderRadius: 2, overflow: "hidden" }}>
        <div style={{
          width: `${pct * 100}%`, height: "100%",
          background: color, borderRadius: 2, transition: "width .4s",
        }} />
      </div>
    </div>
  );
}

function HeroSparkPanel({ ptsSpark, rebSpark, astSpark }) {
  const [activeTab, setActiveTab] = React.useState("PTS");
  const tabs = [
    { key: "PTS", data: ptsSpark, color: "#6366f1" },
    { key: "REB", data: rebSpark, color: "#22c55e" },
    { key: "AST", data: astSpark, color: "#f59e0b" },
  ];
  const active = tabs.find(t => t.key === activeTab);
  const data = active && active.data && active.data.length > 0 ? active.data : null;

  return (
    <div style={{
      padding: "12px 14px", borderRadius: 8,
      background: "#0f0f13", border: "1px solid #2a2a38",
      minWidth: 190, flexShrink: 0,
    }}>
      {/* Tab row */}
      <div style={{ display: "flex", gap: 4, marginBottom: 10 }}>
        {tabs.map(t => (
          <button key={t.key} onClick={() => setActiveTab(t.key)} style={{
            flex: 1, padding: "3px 0", borderRadius: 4,
            background: activeTab === t.key ? "rgba(99,102,241,0.18)" : "transparent",
            border: `1px solid ${activeTab === t.key ? "rgba(99,102,241,0.45)" : "#2a2a38"}`,
            color: activeTab === t.key ? "#c7d2fe" : "#5a5a72",
            fontFamily: "'JetBrains Mono', monospace", fontSize: 9.5, fontWeight: 600,
            cursor: "pointer", transition: "all .12s",
            textTransform: "uppercase", letterSpacing: 0.5,
          }}>{t.key}</button>
        ))}
      </div>
      {/* Sparkline */}
      <Sparkline data={data || [0]} color={active ? active.color : "#6366f1"} w={155} h={28} />
      {/* Stats min/μ/max */}
      <div style={{
        display: "flex", justifyContent: "space-between", marginTop: 4,
        fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: "#8888a0",
      }}>
        {data ? (
          <>
            <span>min {Math.min(...data)}</span>
            <span>μ {(data.reduce((a, b) => a + b, 0) / data.length).toFixed(1)}</span>
            <span>max {Math.max(...data)}</span>
          </>
        ) : (
          <span style={{ color: "#3a3a4a" }}>—</span>
        )}
      </div>
    </div>
  );
}

function Player({ name, navigate, tweaks }) {
  const [player, setPlayer] = React.useState(() => window.NBA_DATA.getPlayer(name));
  const [loadingPlayer, setLoadingPlayer] = React.useState(true);

  React.useEffect(() => {
    let alive = true;
    setLoadingPlayer(true);
    setPlayer(window.NBA_DATA.getPlayer(name));
    fetch(`/api/player/${encodeURIComponent(name)}`)
      .then(r => r.ok ? r.json() : Promise.reject(r.statusText))
      .then(data => { if (alive) { setPlayer(data); setLoadingPlayer(false); } })
      .catch(() => { if (alive) setLoadingPlayer(false); });
    return () => { alive = false; };
  }, [name]);

  const playerProps = window.NBA_DATA.PROPS.filter(
    p => p.player_name.toLowerCase() === name.toLowerCase()
  );

  // Sparklines — recent_games é newest-first; .reverse() → oldest-first para sparkline
  const games = player.recent_games;
  const ptsSpark    = games.map(g => g.pts).reverse();
  const rebSpark    = games.map(g => g.reb).reverse();
  const astSpark    = games.map(g => g.ast).reverse();
  const praSpark    = games.map(g => g.pts + g.reb + g.ast).reverse();
  const prSpark     = games.map(g => g.pts + g.reb).reverse();
  const paSpark     = games.map(g => g.pts + g.ast).reverse();
  const fg3mSpark   = games.map(g => g.fg3m).reverse();
  const stocksSpark = games.map(g => g.blk + g.stl).reverse();

  // Média de minutos para detectar blowouts (min < 80% da média = jogo afetado)
  const avgMin = games.length > 0
    ? games.reduce((s, g) => s + g.min, 0) / games.length
    : 0;

  // Linha de cada prop de hoje para destacar no histórico (apenas OVER)
  const propLines = {};
  for (const p of playerProps) {
    if (p.direction === "OVER" && !(p.market in propLines)) {
      propLines[p.market] = p.line;
    }
  }

  function cellColor(val, market) {
    const line = propLines[market];
    if (line == null) return null;
    if (val > line) return "#4ade80";
    if (val < line) return "#fca5a5";
    return "#fde047";
  }

  if (loadingPlayer && games.length === 0) {
    return (
      <div style={{ minHeight: "100vh", background: "#0f0f13", color: "#e8e8f0", fontFamily: "'Inter Tight', sans-serif" }}>
        <header style={{ position: "sticky", top: 0, zIndex: 10, background: "rgba(15,15,19,0.92)", backdropFilter: "blur(8px)", borderBottom: "1px solid #2a2a38" }}>
          <div style={{ maxWidth: 1280, margin: "0 auto", padding: "14px 28px", display: "flex", alignItems: "center", gap: 16 }}>
            <button onClick={() => navigate("dashboard")} style={{ display: "inline-flex", alignItems: "center", gap: 6, flexShrink: 0, background: "transparent", border: "1px solid #2a2a38", color: "#cbd5e1", padding: "6px 12px", borderRadius: 6, cursor: "pointer", fontFamily: "'Inter Tight', sans-serif", fontSize: 12.5 }}>← Voltar</button>
            <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5, color: "#5a5a72", textTransform: "uppercase", letterSpacing: 0.7 }}>NBA SCOUT / JOGADOR</div>
          </div>
        </header>
        <main style={{ maxWidth: 1280, margin: "0 auto", padding: "28px", display: "flex", flexDirection: "column", gap: 22 }}>
          {/* Skeleton Hero */}
          <section style={{ background: "#1a1a23", border: "1px solid #2a2a38", borderRadius: 10, padding: "22px 26px", display: "flex", alignItems: "center", gap: 22 }}>
            <SkeletonBlock w={64} h={64} style={{ borderRadius: 12, flexShrink: 0 }} />
            <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
              <SkeletonBlock w="55%" h={28} />
              <SkeletonBlock w="30%" h={16} />
            </div>
            <SkeletonBlock w={180} h={62} style={{ borderRadius: 8 }} />
          </section>
          {/* Skeleton Médias */}
          <section>
            <SkeletonBlock w={160} h={12} style={{ marginBottom: 12 }} />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10 }}>
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} style={{ padding: "12px 14px", background: "#1a1a23", border: "1px solid #2a2a38", borderRadius: 7, display: "flex", flexDirection: "column", gap: 8 }}>
                  <SkeletonBlock w="40%" h={10} />
                  <SkeletonBlock w="60%" h={22} />
                </div>
              ))}
            </div>
          </section>
          {/* Skeleton Histórico */}
          <section>
            <SkeletonBlock w={120} h={12} style={{ marginBottom: 12 }} />
            <div style={{ background: "#141419", border: "1px solid #2a2a38", borderRadius: 8, padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
              {Array.from({ length: 6 }).map((_, i) => (
                <SkeletonBlock key={i} w="100%" h={18} />
              ))}
            </div>
          </section>
        </main>
      </div>
    );
  }

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
          maxWidth: 1280, margin: "0 auto", padding: "14px 28px",
          display: "flex", alignItems: "center", gap: 16,
        }}>
          <button onClick={() => navigate("dashboard")} style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            flexShrink: 0, whiteSpace: "nowrap",
            background: "transparent", border: "1px solid #2a2a38", color: "#cbd5e1",
            padding: "6px 12px", borderRadius: 6, cursor: "pointer",
            fontFamily: "'Inter Tight', sans-serif", fontSize: 12.5,
          }}>
            ← Voltar
          </button>

          <div style={{
            fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5,
            color: "#5a5a72", textTransform: "uppercase", letterSpacing: 0.7,
          }}>NBA SCOUT / JOGADOR</div>

          {loadingPlayer && (
            <div style={{
              marginLeft: "auto",
              fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5,
              color: "#5a5a72",
            }}>Carregando…</div>
          )}
        </div>
      </header>

      <main style={{
        maxWidth: 1280, margin: "0 auto", padding: "28px",
        display: "flex", flexDirection: "column", gap: 22,
      }}>
        {/* Hero */}
        <section style={{
          background: "linear-gradient(135deg, #1a1a28 0%, #15151d 100%)",
          border: "1px solid #2a2a38", borderRadius: 12, padding: "24px 28px",
          display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap",
          position: "relative", overflow: "hidden",
        }}>
          {/* Glow de fundo */}
          <div style={{
            position: "absolute", top: -40, left: -40, width: 200, height: 200,
            background: "radial-gradient(circle, rgba(99,102,241,0.08), transparent 70%)",
            pointerEvents: "none",
          }} />
          <div style={{
            width: 68, height: 68, borderRadius: 14, flexShrink: 0,
            background: "linear-gradient(135deg, #3a3a58, #2a2a38)",
            border: "1px solid rgba(99,102,241,0.3)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: "'JetBrains Mono', monospace", fontSize: 22, fontWeight: 700,
            color: "#a5b4fc",
            boxShadow: "0 2px 12px rgba(99,102,241,0.15)",
          }}>
            {player.name.split(" ").map(s => s[0]).slice(0, 2).join("")}
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <h1 style={{
              margin: 0, fontSize: 30, fontWeight: 700, letterSpacing: -0.8,
              fontFamily: "'Inter Tight', sans-serif", lineHeight: 1.1,
              whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
            }}>{player.name}</h1>
            <div style={{
              display: "flex", alignItems: "center", gap: 10,
              flexWrap: "wrap", marginTop: 8,
            }}>
              <span style={{
                padding: "3px 8px", borderRadius: 4,
                background: "rgba(99,102,241,0.14)", border: "1px solid rgba(99,102,241,0.35)",
                fontFamily: "'JetBrains Mono', monospace", fontSize: 11,
                color: "#c7d2fe", fontWeight: 700, letterSpacing: 0.3,
              }}>{player.teamAbbr}</span>
              <span style={{
                fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: "#5a5a72",
              }}>{player.position} · {player.height} · {player.age}a</span>
            </div>
            <div style={{ marginTop: 6, color: "#8888a0", fontSize: 13, fontFamily: "'Inter Tight', sans-serif" }}>{player.team}</div>
          </div>

          {/* Sparklines multi-stat no hero */}
          <HeroSparkPanel ptsSpark={ptsSpark} rebSpark={rebSpark} astSpark={astSpark} />
        </section>

        {/* Grade de médias com sparklines em todas */}
        <section>
          <SectionLabel>Médias (últimos {player.recent_games.length || "—"} jogos)</SectionLabel>
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 10,
          }}>
            <AvgCard label="PTS"    value={player.averages.PTS}    spark={ptsSpark} />
            <AvgCard label="REB"    value={player.averages.REB}    spark={rebSpark} />
            <AvgCard label="AST"    value={player.averages.AST}    spark={astSpark} />
            <AvgCard label="PRA"    value={player.averages.PRA}    spark={praSpark} />
            <AvgCard label="P+R"    value={player.averages.PR}     spark={prSpark} />
            <AvgCard label="P+A"    value={player.averages.PA}     spark={paSpark} />
            <AvgCard label="3PM"    value={player.averages.FG3M}   spark={fg3mSpark} />
            <AvgCard label="STOCKS" value={player.averages.STOCKS} spark={stocksSpark} sub="BLK + STL" />
          </div>
        </section>

        {/* Props de hoje com abas de categoria */}
        {playerProps.length > 0 && (
          <section>
            <SectionLabel>Props hoje · {playerProps.length}</SectionLabel>
            <PropsTabs props={playerProps} oddMode={tweaks.oddMode} recentGames={player.recent_games} />
          </section>
        )}

        {/* Histórico recente com toggle Home/Away */}
        <section>
          <HistorySection
            games={player.recent_games}
            propLines={propLines}
            avgMin={avgMin}
            loadingPlayer={loadingPlayer}
            splits={player.home_away_splits}
            cellColor={cellColor}
          />
        </section>

        {/* Histórico de playoffs */}
        <section>
          <SectionLabel>Histórico de playoffs</SectionLabel>
          <div style={{
            background: "#141419", border: "1px solid #2a2a38",
            borderRadius: 8, overflow: "hidden",
          }}>
            {/* Temporadas badge */}
            {player.playoff_history.seasons.length > 0 && (
              <div style={{
                padding: "10px 16px", borderBottom: "1px solid #2a2a38",
                fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5,
                display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
              }}>
                <span style={{ color: "#5a5a72", textTransform: "uppercase", letterSpacing: 0.7, fontSize: 9 }}>Temporadas</span>
                {player.playoff_history.seasons.map(s => (
                  <span key={s} style={{
                    padding: "2px 7px", borderRadius: 3,
                    background: "rgba(168,85,247,0.1)", border: "1px solid rgba(168,85,247,0.25)",
                    color: "#d8b4fe", fontWeight: 600, fontSize: 10,
                  }}>{s}</span>
                ))}
              </div>
            )}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 0 }}>
              {[
                { label: "Jogos PO",  value: player.playoff_history.games_count, color: "#e8e8f0" },
                { label: "PTS médio", value: Number(player.playoff_history.avg_pts).toFixed(1), color: "#6366f1" },
                { label: "REB médio", value: Number(player.playoff_history.avg_reb).toFixed(1), color: "#22c55e" },
                { label: "AST médio", value: Number(player.playoff_history.avg_ast).toFixed(1), color: "#f59e0b" },
              ].map((item, i, arr) => (
                <div key={item.label} style={{
                  flex: "1 1 120px", padding: "14px 16px",
                  borderRight: i < arr.length - 1 ? "1px solid #2a2a38" : "none",
                }}>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: "#5a5a72", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 6 }}>{item.label}</div>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 22, fontWeight: 700, color: item.color, letterSpacing: -0.5 }}>{item.value}</div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

function HistorySection({ games, propLines, avgMin, loadingPlayer, splits, cellColor }) {
  const [locFilter, setLocFilter] = React.useState("ALL");
  const filtered = locFilter === "ALL" ? games
    : games.filter(g => g.home_away === locFilter);

  const tabStyle = (key) => ({
    padding: "3px 12px", borderRadius: 20,
    background: locFilter === key ? "rgba(99,102,241,0.2)" : "transparent",
    border: `1px solid ${locFilter === key ? "rgba(99,102,241,0.55)" : "#2a2a38"}`,
    color: locFilter === key ? "#c7d2fe" : "#8888a0",
    fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5,
    cursor: "pointer", transition: "all .12s",
  });

  const s = splits || {};
  const hasLocationData = (s.home_games || 0) + (s.away_games || 0) > 0;

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <div style={{
          fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5, color: "#5a5a72",
          textTransform: "uppercase", letterSpacing: 1,
        }}>Histórico recente</div>
        <span style={{ flex: 1, height: 1, background: "#2a2a38" }} />
        {Object.keys(propLines).length > 0 && (
          <span style={{ fontSize: 10, color: "#5a5a72", fontWeight: 400 }}>
            células coloridas = linha do prop
          </span>
        )}
        <button style={tabStyle("ALL")} onClick={() => setLocFilter("ALL")}>Todos</button>
        <button style={tabStyle("home")} onClick={() => setLocFilter("home")}>Casa</button>
        <button style={tabStyle("away")} onClick={() => setLocFilter("away")}>Fora</button>
      </div>

      {/* Mini comparativo Casa vs Fora */}
      {hasLocationData && (
        <div style={{
          display: "flex", gap: 16, marginBottom: 10, padding: "10px 14px",
          background: "#141419", border: "1px solid #2a2a38", borderRadius: 7,
          fontFamily: "'JetBrains Mono', monospace", fontSize: 11, flexWrap: "wrap",
        }}>
          <span style={{ color: "#5a5a72" }}>
            Casa ({s.home_games}j):
            <span style={{ color: "#4ade80", marginLeft: 6 }}>PTS {(s.home_avg_pts || 0).toFixed(1)}</span>
            <span style={{ color: "#93c5fd", marginLeft: 8 }}>REB {(s.home_avg_reb || 0).toFixed(1)}</span>
            <span style={{ color: "#c4b5fd", marginLeft: 8 }}>AST {(s.home_avg_ast || 0).toFixed(1)}</span>
          </span>
          <span style={{ color: "#3a3a4a" }}>|</span>
          <span style={{ color: "#5a5a72" }}>
            Fora ({s.away_games}j):
            <span style={{ color: "#4ade80", marginLeft: 6 }}>PTS {(s.away_avg_pts || 0).toFixed(1)}</span>
            <span style={{ color: "#93c5fd", marginLeft: 8 }}>REB {(s.away_avg_reb || 0).toFixed(1)}</span>
            <span style={{ color: "#c4b5fd", marginLeft: 8 }}>AST {(s.away_avg_ast || 0).toFixed(1)}</span>
          </span>
        </div>
      )}

      <div style={{
            background: "#141419", border: "1px solid #2a2a38",
            borderRadius: 8, overflow: "hidden",
          }}>
            <div style={{ overflowX: "auto", overflowY: "auto", maxHeight: 480 }}>
            <table style={{
              width: "100%", borderCollapse: "collapse",
              fontFamily: "'JetBrains Mono', monospace", fontSize: 12.5,
            }}>
              <thead style={{ background: "#0f0f13", position: "sticky", top: 0, zIndex: 2 }}>
                <tr>
                  {["DATA", "PO", "ADV", "MAR", "MIN", "PTS", "REB", "AST", "3PM", "BLK", "STL"].map(h => (
                    <th key={h} style={{
                      padding: "10px 12px",
                      textAlign: h === "DATA" || h === "ADV" ? "left" : "right",
                      fontSize: 10, color: "#5a5a72", fontWeight: 500,
                      textTransform: "uppercase", letterSpacing: 0.7,
                      borderBottom: "1px solid #2a2a38",
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 && (
                  <tr><td colSpan={11} style={{
                    padding: 32, textAlign: "center", color: "#3a3a4a",
                    fontFamily: "'Inter Tight', sans-serif",
                  }}>
                    {loadingPlayer ? "Carregando…" : locFilter === "ALL" ? "Sem jogos disponíveis" : "Sem jogos neste contexto"}
                  </td></tr>
                )}
                {filtered.map((g, i) => {
                  const ptsC  = cellColor(g.pts,  "PTS");
                  const rebC  = cellColor(g.reb,  "REB");
                  const astC  = cellColor(g.ast,  "AST");
                  const fg3mC = cellColor(g.fg3m, "FG3M");
                  const blkC  = cellColor(g.blk,  "BLK");
                  const stlC  = cellColor(g.stl,  "STL");
                  return (
                    <tr key={i} style={{
                      background: i % 2 ? "#141419" : "#161620",
                      borderBottom: "1px solid rgba(42,42,56,0.4)",
                    }}>
                      <td style={{ padding: "10px 12px", color: "#cbd5e1" }}>{g.date}</td>
                      <td style={{ padding: "10px 12px" }}>
                        {g.is_playoff ? (
                          <span style={{
                            padding: "2px 7px", borderRadius: 3,
                            background: "rgba(168,85,247,0.15)",
                            border: "1px solid rgba(168,85,247,0.35)",
                            color: "#d8b4fe", fontSize: 9.5, fontWeight: 700, letterSpacing: 0.5,
                          }}>PO</span>
                        ) : (
                          <span style={{ color: "#3a3a4a" }}>—</span>
                        )}
                      </td>
                      <td style={{ padding: "10px 12px", color: "#8888a0" }}>{g.opp}</td>
                      <td style={{ padding: "10px 12px", textAlign: "right" }}>
                        {(() => {
                          if (!g.margin && g.margin !== 0) return <span style={{ color: "#3a3a4a" }}>—</span>;
                          const isBlowout = Math.abs(g.margin) > 15;
                          const lowMin = avgMin > 0 && g.min < avgMin * 0.8;
                          const color = g.margin > 0 ? "#4ade80" : g.margin < 0 ? "#fca5a5" : "#8888a0";
                          return (
                            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                              <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11.5, color }}>
                                {g.margin > 0 ? "+" : ""}{g.margin}
                              </span>
                              {isBlowout && lowMin && (
                                <span style={{
                                  padding: "1px 5px", borderRadius: 3,
                                  background: "rgba(234,179,8,0.15)",
                                  border: "1px solid rgba(234,179,8,0.35)",
                                  color: "#fde047", fontSize: 9, fontWeight: 700, letterSpacing: 0.4,
                                }}>BLW</span>
                              )}
                            </span>
                          );
                        })()}
                      </td>
                      <td style={{ padding: "10px 12px", textAlign: "right", color: "#8888a0" }}>{g.min}</td>
                      <td style={{ padding: "10px 12px", textAlign: "right", color: ptsC || "#e8e8f0", fontWeight: ptsC ? 700 : 600 }}>{g.pts}</td>
                      <td style={{ padding: "10px 12px", textAlign: "right", color: rebC || undefined }}>{g.reb}</td>
                      <td style={{ padding: "10px 12px", textAlign: "right", color: astC || undefined }}>{g.ast}</td>
                      <td style={{ padding: "10px 12px", textAlign: "right", color: fg3mC || "#8888a0" }}>{g.fg3m}</td>
                      <td style={{ padding: "10px 12px", textAlign: "right", color: blkC || "#8888a0" }}>{g.blk}</td>
                      <td style={{ padding: "10px 12px", textAlign: "right", color: stlC || "#8888a0" }}>{g.stl}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </div>
          </div>
    </>
  );
}

const PROP_CATEGORIES = [
  { key: "ALL",    label: "Todos",   markets: null },
  { key: "SIMPLE", label: "Simples", markets: new Set(["PTS", "REB", "AST", "FG3M", "BLK", "STL"]) },
  { key: "COMBO",  label: "Combos",  markets: new Set(["PRA", "PR", "PA", "RA", "STOCKS"]) },
];

function PropsTabs({ props, oddMode, recentGames }) {
  const [activeTab, setActiveTab] = React.useState("ALL");
  const cat = PROP_CATEGORIES.find(c => c.key === activeTab);
  const visible = cat && cat.markets
    ? props.filter(p => cat.markets.has(p.market))
    : props;

  const tabStyle = (key) => ({
    padding: "5px 14px", borderRadius: 20,
    background: activeTab === key ? "rgba(99,102,241,0.2)" : "transparent",
    border: `1px solid ${activeTab === key ? "rgba(99,102,241,0.55)" : "#2a2a38"}`,
    color: activeTab === key ? "#c7d2fe" : "#8888a0",
    fontFamily: "'JetBrains Mono', monospace", fontSize: 11.5,
    fontWeight: activeTab === key ? 600 : 400,
    cursor: "pointer", transition: "all .12s",
  });

  return (
    <div>
      <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
        {PROP_CATEGORIES.map(c => {
          const count = c.markets ? props.filter(p => c.markets.has(p.market)).length : props.length;
          return (
            <button key={c.key} onClick={() => setActiveTab(c.key)} style={tabStyle(c.key)}>
              {c.label}
              {count > 0 && <span style={{ marginLeft: 6, fontSize: 10, opacity: 0.7 }}>{count}</span>}
            </button>
          );
        })}
      </div>
      {visible.length > 0 ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 10 }}>
          {visible.map((p, i) => (
            <PlayerPropCard key={i} prop={p} oddMode={oddMode} recentGames={recentGames} />
          ))}
        </div>
      ) : (
        <div style={{
          padding: 32, textAlign: "center", color: "#3a3a4a",
          fontFamily: "'Inter Tight', sans-serif",
          background: "#141419", border: "1px dashed #2a2a38", borderRadius: 8,
        }}>Nenhum prop nessa categoria</div>
      )}
    </div>
  );
}

function AvgCard({ label, value, sub, spark }) {
  const STAT_COLORS = {
    PTS: "#6366f1", REB: "#22c55e", AST: "#f59e0b",
    PRA: "#8b5cf6", "P+R": "#3b82f6", "P+A": "#06b6d4",
    "3PM": "#ec4899", STOCKS: "#f97316",
  };
  const color = STAT_COLORS[label] || "#6366f1";
  return (
    <div style={{
      padding: "12px 14px",
      background: "#1a1a23", border: "1px solid #2a2a38", borderRadius: 8,
      position: "relative", overflow: "hidden",
      transition: "border-color .15s",
    }}
    onMouseEnter={e => e.currentTarget.style.borderColor = "#3a3a4a"}
    onMouseLeave={e => e.currentTarget.style.borderColor = "#2a2a38"}>
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 2, background: color, opacity: 0.6 }} />
      <div style={{
        fontFamily: "'JetBrains Mono', monospace", fontSize: 9, color: "#5a5a72",
        textTransform: "uppercase", letterSpacing: 1, marginBottom: 6,
      }}>{label}</div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 8 }}>
        <div style={{
          fontFamily: "'JetBrains Mono', monospace", fontSize: 23,
          fontWeight: 700, color: "#e8e8f0", lineHeight: 1, letterSpacing: -0.5,
        }}>{Number(value).toFixed(1)}</div>
        {spark && spark.length > 0 && <Sparkline data={spark} color={color} w={52} h={20} />}
      </div>
      {sub && (
        <div style={{
          fontSize: 9.5, color: "#5a5a72", marginTop: 5,
          fontFamily: "'JetBrains Mono', monospace",
        }}>{sub}</div>
      )}
    </div>
  );
}

function Stat2({ label, value, sub }) {
  return (
    <div style={{ minWidth: 110 }}>
      <div style={{
        fontFamily: "'JetBrains Mono', monospace", fontSize: 9.5, color: "#5a5a72",
        textTransform: "uppercase", letterSpacing: 0.7, marginBottom: 4,
      }}>{label}</div>
      <div style={{
        fontFamily: "'JetBrains Mono', monospace", fontSize: 18,
        fontWeight: 600, color: "#e8e8f0",
      }}>{value}</div>
      {sub && (
        <div style={{
          fontSize: 10.5, color: "#8888a0", marginTop: 3,
          fontFamily: "'JetBrains Mono', monospace",
        }}>{sub}</div>
      )}
    </div>
  );
}

function PlayerPropCard({ prop, oddMode, recentGames }) {
  const evColor = prop.ev_pct >= 8 ? "#4ade80" : prop.ev_pct > 0 ? "#86efac" : "#fca5a5";
  const t = RATING_TOKENS[prop.rating] || RATING_TOKENS.NEUTRAL;
  const isStrong = prop.rating === "STRONG";

  let hitData = null;
  let sparkData = null;
  if (recentGames && recentGames.length > 0) {
    const vals = recentGames
      .map(g => getStatValue(g, prop.market))
      .filter(v => v != null);
    if (vals.length > 0) {
      const hit = prop.direction === "OVER"
        ? vals.filter(v => v > prop.line).length
        : vals.filter(v => v < prop.line).length;
      hitData = { hit, total: vals.length };
      sparkData = [...vals].reverse();
    }
  }

  return (
    <div style={{
      background: isStrong ? "linear-gradient(180deg, #1c1c2a 0%, #161620 100%)" : "#1a1a23",
      border: `1px solid ${isStrong ? "rgba(99,102,241,0.38)" : "#2a2a38"}`,
      borderRadius: 10, padding: 14, position: "relative", overflow: "hidden",
      transition: "border-color .15s",
    }}
    onMouseEnter={e => e.currentTarget.style.borderColor = isStrong ? "rgba(99,102,241,0.6)" : "#3a3a4a"}
    onMouseLeave={e => e.currentTarget.style.borderColor = isStrong ? "rgba(99,102,241,0.38)" : "#2a2a38"}>
      {/* Accent bar */}
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 3, background: t.dot }} />
      {isStrong && (
        <div style={{
          position: "absolute", top: 0, right: 0, width: 80, height: 80,
          background: "radial-gradient(circle, rgba(99,102,241,0.12), transparent 70%)",
          pointerEvents: "none",
        }} />
      )}

      {/* Header */}
      <div style={{
        display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0, flex: 1 }}>
          <span style={{
            fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: "#8888a0",
            whiteSpace: "nowrap",
          }}>{prop.game}</span>
          {prop.dvp_rank > 0 && prop.dvp_total > 0 && (
            <Tooltip text={`Defesa vs posição: ${prop.dvp_rank}º/${prop.dvp_total} — rank 1 = pior defesa (melhor matchup)`}>
              <span style={{
                padding: "1px 6px", borderRadius: 3, fontSize: 9.5, fontWeight: 600,
                background: prop.dvp_rank <= 10 ? "rgba(74,222,128,0.12)" : prop.dvp_rank <= 20 ? "rgba(253,224,71,0.1)" : "rgba(239,68,68,0.1)",
                border: `1px solid ${prop.dvp_rank <= 10 ? "rgba(74,222,128,0.35)" : prop.dvp_rank <= 20 ? "rgba(253,224,71,0.3)" : "rgba(239,68,68,0.3)"}`,
                color: prop.dvp_rank <= 10 ? "#4ade80" : prop.dvp_rank <= 20 ? "#fde047" : "#fca5a5",
                whiteSpace: "nowrap",
              }}>DvP {prop.dvp_rank}°/{prop.dvp_total}</span>
            </Tooltip>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
          <StarButton prop={prop} />
          <RatingBadge rating={prop.rating} />
        </div>
      </div>

      {/* Linha / mercado */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8, marginBottom: 12,
        padding: "9px 11px", background: "#0f0f13", borderRadius: 6,
        border: "1px solid rgba(42,42,56,0.6)",
        fontFamily: "'JetBrains Mono', monospace",
      }}>
        <span style={{
          padding: "2px 7px", borderRadius: 3,
          background: "rgba(90,90,114,0.15)", border: "1px solid rgba(90,90,114,0.25)",
          fontSize: 9.5, color: "#5a5a72", textTransform: "uppercase", letterSpacing: 0.5, fontWeight: 600,
        }}>{prop.market}</span>
        <span style={{
          color: prop.direction === "OVER" ? "#86efac" : "#fca5a5",
          fontSize: 11.5, fontWeight: 700, letterSpacing: 0.3,
        }}>{prop.direction}</span>
        <span style={{ color: "#e8e8f0", fontSize: 22, fontWeight: 700, letterSpacing: -0.5 }}>{prop.line}</span>
        <span style={{ flex: 1 }} />
        <span style={{ color: "#a0a0c0", fontSize: 12 }}>{fmtOdd(prop.odd, oddMode)}</span>
      </div>

      {/* Stats row */}
      <div style={{
        display: "flex", justifyContent: "space-between",
        fontFamily: "'JetBrains Mono', monospace", fontSize: 11.5, marginBottom: sparkData ? 0 : 0,
      }}>
        <Tooltip text="Expected Value: positivo = odd acima do valor justo.">
          <span style={{ color: "#5a5a72" }}>EV <span style={{ color: evColor, fontWeight: 700 }}>{fmtPct(prop.ev_pct)}</span></span>
        </Tooltip>
        <Tooltip text="Probabilidade real estimada (forma recente + média de temporada).">
          <span style={{ color: "#5a5a72" }}>Prob <span style={{ color: "#cbd5e1" }}>{fmtProb(prop.prob_real)}</span></span>
        </Tooltip>
        <Tooltip text="Fração de bankroll pelo critério de Kelly. Use como referência.">
          <span style={{ color: "#5a5a72" }}>Kelly <span style={{ color: "#a5b4fc" }}>{prop.kelly_pct.toFixed(1)}%</span></span>
        </Tooltip>
      </div>

      {/* Sparkline de tendência */}
      {sparkData && sparkData.length > 1 && (
        <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid #2a2a38" }}>
          <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9.5, color: "#5a5a72", marginBottom: 5 }}>
            Tendência · {sparkData.length} jogos
          </div>
          <Sparkline data={sparkData} color={evColor === "#4ade80" ? "#4ade80" : "#6366f1"} w={220} h={38} line={prop.line} />
        </div>
      )}

      {/* Hit rate bar */}
      {hitData && (
        <HitRateBar
          hit={hitData.hit}
          total={hitData.total}
          line={prop.line}
          direction={prop.direction}
        />
      )}
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

Object.assign(window, { Player });
