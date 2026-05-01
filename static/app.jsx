// App shell — roteamento entre Dashboard e Player, com loading state da API

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "variation": "terminal",
  "oddMode": "decimal"
}/*EDITMODE-END*/;

function LoadingScreen() {
  return (
    <div style={{
      minHeight: "100vh", background: "#0f0f13", color: "#8888a0",
      display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", gap: 16,
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      <div style={{
        width: 40, height: 40, borderRadius: 10, flexShrink: 0,
        background: "linear-gradient(135deg, #6366f1, #4f46e5)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 16, fontWeight: 700, color: "#fff",
      }}>NS</div>
      <div style={{ fontSize: 12, letterSpacing: 0.5, color: "#5a5a72" }}>
        Buscando props de hoje…
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        {[0, 1, 2].map(i => (
          <span key={i} style={{
            display: "inline-block", width: 6, height: 6, borderRadius: "50%",
            background: "#6366f1", opacity: 0.2,
            animation: `nbaPulse 1.2s ease-in-out ${i * 0.2}s infinite`,
          }} />
        ))}
      </div>
      <style>{`
        @keyframes nbaPulse {
          0%, 80%, 100% { opacity: 0.2; }
          40%            { opacity: 1;   }
        }
      `}</style>
    </div>
  );
}

function ErrorScreen({ error, onRetry }) {
  return (
    <div style={{
      minHeight: "100vh", background: "#0f0f13",
      display: "flex", flexDirection: "column", alignItems: "center",
      justifyContent: "center", gap: 18, padding: 32, textAlign: "center",
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      <div style={{
        padding: "14px 20px", borderRadius: 8,
        background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)",
        fontSize: 12, color: "#fca5a5", maxWidth: 480, lineHeight: 1.6,
      }}>
        Erro ao buscar props:<br />{error}
      </div>
      <button onClick={onRetry} style={{
        padding: "8px 20px", borderRadius: 6,
        background: "#6366f1", border: "1px solid #4f46e5", color: "#fff",
        fontFamily: "inherit", fontSize: 12, fontWeight: 600, cursor: "pointer",
      }}>
        Tentar novamente
      </button>
    </div>
  );
}

function App() {
  const [status, setStatus] = React.useState("loading"); // "loading" | "ready" | "error"
  const [errorMsg, setErrorMsg] = React.useState(null);
  const [route, setRoute] = React.useState(
    () => window.location.hash.slice(1) || "dashboard"
  );

  React.useEffect(() => {
    const onHash = () => setRoute(window.location.hash.slice(1) || "dashboard");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const loadData = React.useCallback(() => {
    setStatus("loading");
    window.NBA_DATA.init((err) => {
      if (err) { setErrorMsg(err.message); setStatus("error"); }
      else      setStatus("ready");
    });
  }, []);

  React.useEffect(() => { loadData(); }, [loadData]);

  const navigate = (target) => { window.location.hash = target; };
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);

  if (status === "loading") return <LoadingScreen />;
  if (status === "error")   return <ErrorScreen error={errorMsg} onRetry={loadData} />;

  let view;
  if (route.startsWith("player/")) {
    const name = decodeURIComponent(route.slice("player/".length));
    view = <Player name={name} navigate={navigate} tweaks={tweaks} />;
  } else {
    view = <Dashboard navigate={navigate} tweaks={tweaks} setTweak={setTweak} />;
  }

  return (
    <>
      {view}
      <TweaksPanel title="Tweaks">
        <TweakSection title="Layout">
          <TweakRadio label="Variação"
            value={tweaks.variation}
            onChange={v => setTweak("variation", v)}
            options={[
              { value: "terminal",  label: "Terminal"  },
              { value: "cards",     label: "Cards"     },
              { value: "editorial", label: "Editorial" },
            ]} />
        </TweakSection>
        <TweakSection title="Formato">
          <TweakRadio label="Odds"
            value={tweaks.oddMode}
            onChange={v => setTweak("oddMode", v)}
            options={[
              { value: "decimal", label: "Decimais"    },
              { value: "implied", label: "% Implícita" },
            ]} />
        </TweakSection>
      </TweaksPanel>
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
