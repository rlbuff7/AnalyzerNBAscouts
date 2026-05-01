// Favoritos / Watchlist — persiste em localStorage

const NBA_FAVORITES = (() => {
  const KEY = "nba-scout-favorites";

  function load() {
    try { return new Set(JSON.parse(localStorage.getItem(KEY) || "[]")); }
    catch { return new Set(); }
  }

  function save(set) {
    localStorage.setItem(KEY, JSON.stringify([...set]));
  }

  function propKey(prop) {
    return `${prop.player_name}|${prop.market}|${prop.line}|${prop.direction}`;
  }

  function toggle(prop) {
    const s = load();
    const k = propKey(prop);
    if (s.has(k)) s.delete(k); else s.add(k);
    save(s);
    window.dispatchEvent(new CustomEvent("nba-favorites-changed"));
  }

  function has(prop) { return load().has(propKey(prop)); }
  function count() { return load().size; }

  return { load, toggle, has, count, propKey };
})();

function StarButton({ prop, style = {} }) {
  const [fav, setFav] = React.useState(() => NBA_FAVORITES.has(prop));

  React.useEffect(() => {
    const onUpdate = () => setFav(NBA_FAVORITES.has(prop));
    window.addEventListener("nba-favorites-changed", onUpdate);
    return () => window.removeEventListener("nba-favorites-changed", onUpdate);
  }, [prop]);

  return (
    <button
      onClick={e => { e.stopPropagation(); NBA_FAVORITES.toggle(prop); }}
      title={fav ? "Remover dos favoritos" : "Adicionar aos favoritos"}
      style={{
        background: "none", border: "none", cursor: "pointer",
        padding: "2px 4px", lineHeight: 1, fontSize: 14,
        color: fav ? "#fde047" : "#3a3a4a",
        transition: "color .15s, transform .1s",
        transform: fav ? "scale(1.15)" : "scale(1)",
        ...style,
      }}
      onMouseEnter={e => { if (!fav) e.currentTarget.style.color = "#8888a0"; }}
      onMouseLeave={e => { if (!fav) e.currentTarget.style.color = "#3a3a4a"; }}
    >★</button>
  );
}

Object.assign(window, { NBA_FAVORITES, StarButton });
