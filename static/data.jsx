// data.jsx — inicialização de dados via API real
// Substitui o mock do protótipo por fetch em /api/props e /api/player/{name}.

const TEAMS = {
  BOS: { name: "Boston Celtics",          abbr: "BOS" },
  CLE: { name: "Cleveland Cavaliers",     abbr: "CLE" },
  DEN: { name: "Denver Nuggets",          abbr: "DEN" },
  MIN: { name: "Minnesota Timberwolves",  abbr: "MIN" },
  OKC: { name: "Oklahoma City Thunder",   abbr: "OKC" },
  DAL: { name: "Dallas Mavericks",        abbr: "DAL" },
  NYK: { name: "New York Knicks",         abbr: "NYK" },
  IND: { name: "Indiana Pacers",          abbr: "IND" },
  PHI: { name: "Philadelphia 76ers",      abbr: "PHI" },
  MIL: { name: "Milwaukee Bucks",         abbr: "MIL" },
  LAL: { name: "Los Angeles Lakers",      abbr: "LAL" },
  PHX: { name: "Phoenix Suns",            abbr: "PHX" },
  GSW: { name: "Golden State Warriors",   abbr: "GSW" },
  MIA: { name: "Miami Heat",              abbr: "MIA" },
  ORL: { name: "Orlando Magic",           abbr: "ORL" },
};

const MARKETS = [
  { key: "ALL",    label: "Todos"        },
  { key: "PTS",    label: "Pontos"       },
  { key: "REB",    label: "Rebotes"      },
  { key: "AST",    label: "Assistências" },
  { key: "FG3M",   label: "3PM"          },
  { key: "BLK",    label: "Bloqueios"    },
  { key: "STL",    label: "Roubos"       },
  { key: "PRA",    label: "PRA"          },
  { key: "PR",     label: "PR"           },
  { key: "PA",     label: "PA"           },
  { key: "RA",     label: "RA"           },
  { key: "STOCKS", label: "Stocks"       },
];

// Retorna um stub vazio enquanto os dados do jogador ainda não foram buscados da API
function getPlayer(name) {
  const prop = (window.NBA_DATA.PROPS || []).find(
    p => p.player_name.toLowerCase() === name.toLowerCase()
  );
  const team = prop?.team || "—";
  return {
    id: 0,
    name,
    team,
    teamAbbr: team,
    position: "—",
    height: "—",
    age: "—",
    averages: { PTS: 0, REB: 0, AST: 0, PRA: 0, PR: 0, PA: 0, FG3M: 0, STOCKS: 0 },
    spark: [],
    recent_games: [],
    playoff_history: { seasons: [], games_count: 0, avg_pts: 0, avg_reb: 0, avg_ast: 0 },
  };
}

window.NBA_DATA = {
  TEAMS,
  MARKETS,
  PROPS: [],
  GENERATED_AT: new Date().toISOString(),
  QUOTA_REMAINING: 0,
  QUOTA_LIMIT: 500,
  FROM_CACHE: false,
  DEMO_MODE: false,
  loading: true,
  error: null,
  getPlayer,

  // Chamado por app.jsx na montagem; popula PROPS a partir de /api/props
  async init(onDone) {
    try {
      const res = await fetch("/api/props");
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      const data = await res.json();
      window.NBA_DATA.PROPS           = data.props           || [];
      window.NBA_DATA.GENERATED_AT    = data.generated_at    || new Date().toISOString();
      window.NBA_DATA.QUOTA_REMAINING = data.quota_remaining ?? 0;
      window.NBA_DATA.QUOTA_LIMIT     = data.quota_limit     ?? 500;
      window.NBA_DATA.FROM_CACHE      = data.from_cache      ?? false;
      window.NBA_DATA.DEMO_MODE       = data.demo_mode       ?? false;
      window.NBA_DATA.loading = false;
      onDone(null);
    } catch (err) {
      window.NBA_DATA.loading = false;
      window.NBA_DATA.error = err.message;
      onDone(err);
    }
  },
};
