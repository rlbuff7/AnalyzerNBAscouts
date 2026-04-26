# NBA Scout — EV Analyzer

Ferramenta CLI em Python que analisa **player props** da NBA em tempo real e identifica apostas com **valor esperado positivo (EV+)**.

Cruza estatísticas reais dos jogadores (via ESPN API, sem bloqueio geográfico) com odds ao vivo da Bet365/Pinnacle (via The Odds API) para calcular probabilidade real, EV%, Kelly fracionado e classificar cada prop como `strong`, `value`, `neutral` ou `avoid`.

Funciona direto do **Brasil** sem VPN.

---

## Instalação

**Requisitos:** Python 3.11+

```bash
git clone https://github.com/rlbuff7/AnalyzerNBAscouts.git
cd AnalyzerNBAscouts
pip install -r requirements.txt
```

Crie o arquivo `.env` na raiz:

```bash
cp .env.example .env
```

Edite `.env` com sua chave:

```
ODDS_API_KEY=sua_chave_aqui
```

### Obtendo a chave da Odds API

Acesse [the-odds-api.com](https://the-odds-api.com) e crie uma conta gratuita.  
O **free tier** dá **500 requests/mês** — suficiente para rodar toda semana de playoffs e temporada regular com folga.

---

## Uso

### Modo interativo (recomendado)

```bash
python main.py -i
```

Abre um menu com setas para navegar:

```
? O que deseja fazer?
  > Analisar o dia (props ao vivo)
    Buscar por jogador
    Ver resultados salvos (cache)
    Sair
```

**Analisar o dia** — busca todos os jogos e props do dia, pergunta por mercado, EV mínimo e se quer só strong bets. Se já tiver resultados da sessão, oferece reutilizá-los sem gastar quota da API.

**Buscar por jogador** — digita o nome (parcial funciona: "jokic", "lebron"), mostra:
- Histórico dos últimos 10 jogos com PTS/REB/AST/3PM/BLK/STL por jogo
- Médias individuais e combinadas (PRA, P+R, P+A, etc.)
- Médias históricas de playoffs de temporadas anteriores
- Props do jogador disponíveis no último cache com EV% e rating
- Jogos de playoffs aparecem destacados em roxo

**Ver resultados salvos** — filtra o último resultado salvo sem nova chamada à API.

---

### Modo linha de comando

```bash
# análise completa do dia
python main.py

# só strong bets (EV >= 8% e prob real >= 60%)
python main.py --only-strong

# filtrar por mercado
python main.py --market points
python main.py --market pra
python main.py --market stocks

# EV mínimo customizado
python main.py --market rebounds --min-ev 5

# exportar resultado em JSON
python main.py --export

# logging detalhado
python main.py --verbose
```

### Mercados disponíveis

| Flag `--market` | Mercado | Estatística |
|---|---|---|
| `points` | Pontos | PTS |
| `rebounds` | Rebotes | REB |
| `assists` | Assistências | AST |
| `threes` | 3 Pontos | FG3M |
| `blocks` | Bloqueios | BLK |
| `steals` | Roubos | STL |
| `pra` | Pts + Reb + Ast | PRA |
| `pr` | Pts + Reb | PR |
| `pa` | Pts + Ast | PA |
| `ra` | Reb + Ast | RA |
| `stocks` | Blk + Stl | STOCKS |

> Mercados de soma (PRA, PR, PA, etc.) são calculados jogo a jogo no histórico real do jogador — não é só somar médias.

### Todas as opções

| Flag | Padrão | Descrição |
|---|---|---|
| `-i` / `--interactive` | off | Modo interativo com menu |
| `--market` | `all` | Filtrar por mercado (ver tabela acima) |
| `--min-ev N` | `3.0` | EV% mínimo para exibir |
| `--only-strong` | off | Apenas entradas `strong` (EV ≥ 8% e prob ≥ 60%) |
| `--export` | off | Salva `scout_output.json` no diretório |
| `--verbose` / `-v` | off | Logging detalhado |

---

## Como o EV é calculado

### 1. Probabilidade real do jogador

A probabilidade de o jogador superar a linha é estimada combinando:

**a) Frequência histórica** — fração dos últimos 10 jogos em que o jogador bateu a linha para aquele mercado.  
Se o jogador está em playoffs, os jogos de playoff da temporada atual têm prioridade; slots restantes são preenchidos com jogos recentes de temporada regular.

**b) Blend com histórico de playoffs** — se há dados de playoffs de temporadas anteriores (≥ 3 jogos), a probabilidade é misturada:

```
prob_final = prob_atual × 0.65 + prob_histórica_playoffs × 0.35
```

**c) Ajuste por defesa do adversário** — baseado no defensive rating do time adversário comparado à média da liga (112):

| Situação | Ajuste |
|---|---|
| def_rating ≥ média + 4 (defesa ruim) | +4% |
| def_rating ≥ média | +2% |
| def_rating ≤ média − 2 (defesa boa) | −3% |
| def_rating ≤ média − 6 (defesa elite) | −5% |

**d) Ajuste por pace** — times com ritmo alto (+2-3%) ou baixo (−2%) afetam props de volume.

**e) Ajuste por minutos** — jogadores com < 28 min médios têm −3% em overs de pontos.

**f) Clamp** — probabilidade limitada entre **25%** e **85%** para evitar extremos.

### 2. Probabilidade implícita da casa

```
prob_casa = 1 / odd_decimal
```

A odd embute uma margem de ~5-8% a favor da casa.

### 3. Valor esperado

```
EV% = (prob_real × (odd - 1) - (1 - prob_real)) × 100
```

Se `EV% > 0` a aposta tem valor matemático positivo no longo prazo.

### 4. Kelly fracionado (sugestão de stake)

```
kelly = (prob_real × b − (1 − prob_real)) / b    onde b = odd − 1
stake_sugerida = kelly / 4    (Kelly fracionado conservador)
```

### Classificação

| Rating | Critério |
|---|---|
| `STRONG` | EV ≥ 8% **e** prob real ≥ 60% |
| `VALUE` | EV ≥ 3% |
| `NEUTRAL` | EV entre −1% e 3% |
| `AVOID` | EV < −1% |

---

## Fontes de dados

| Dado | Fonte | Observação |
|---|---|---|
| Jogos do dia | `data.nba.com` (nba_api) | Sem bloqueio geográfico |
| Stats dos jogadores | ESPN API (não oficial) | Sem autenticação, sem geoblock |
| Histórico de playoffs | ESPN API (temporadas anteriores) | Cacheado por 24h |
| Pace e defesa dos times | ESPN API (team statistics) | Cacheado por 24h |
| Odds / props ao vivo | The Odds API v4 | Requer ODDS_API_KEY |

### Cache local (`.cache/`)

Para evitar chamadas repetidas e economizar quota:

| Arquivo | Conteúdo | TTL |
|---|---|---|
| `player_index.json` | Índice de ~2000 jogadores ativos | 24h |
| `team_stats.json` | Pace e def_rating de todos os times | 24h |
| `po_hist_{id}_{ano}.json` | Stats de playoffs de temporadas anteriores | 24h |
| `partial_results.json` | Último resultado da análise (salvo por jogo) | Substituído a cada análise |

---

## Estrutura do projeto

```
AnalyzerNBAscouts/
├── main.py          # Entry point — CLI e modo interativo
├── interactive.py   # TUI com questionary (modo -i)
├── scout.py         # Orquestração: busca jogos, props, cruza tudo
├── stats.py         # ESPN API: jogadores, gamelog, histórico playoffs, times
├── odds.py          # The Odds API: eventos do dia e props por jogo
├── ev.py            # EV, Kelly, probabilidade real, classificação
├── report.py        # Tabela Rich no terminal + export JSON
├── config.py        # Constantes, chaves, mapeamentos de times e mercados
├── requirements.txt
├── .env.example
└── README.md
```

---

## Exemplo de saída

```
╭──────────────────────────────────────────────────╮
│ NBA Scout — EV Analyzer                          │
│ Data: 2026-04-26    Entradas: 31    EV+: 18    Strong: 4 │
╰──────────────────────────────────────────────────╯
Odds API quota restante: 412

              Análise de Player Props
 Jogador          Jogo   Mercado  Linha  Dir    Odd   Prob Real   EV%    Kelly%  Rating   Casa
 ─────────────────────────────────────────────────────────────────────────────────────────────
 D. Mitchell      vs CLE  PRA     39.5   OVER  1.87    72.0%   +22.6%   5.6%   STRONG   pinnacle
 J. Harden        vs MIN  Pontos  20.5   OVER  1.97    68.0%   +18.2%   4.5%   STRONG   pinnacle
 ...
```

---

## Quota da Odds API

Cada análise completa consome:
- **1 request** para listar eventos do dia
- **~1 request por jogo** para buscar props (com todos os mercados em uma chamada)

Em dia típico de playoffs (5-6 jogos): **~7 requests**.  
Com free tier de **500 req/mês** dá para rodar **1-2 vezes por dia** durante toda a temporada.

O scout para automaticamente se restam **< 10 requests** e avisa o quota restante a cada análise.

---

## Troubleshooting

### Nenhuma prop retornada para steals/blocks/combos

Mercados como `player_steals`, `player_blocks` e `player_blocks_steals` são menos comuns em casas européias (Bet365/Pinnacle EU). Se a análise retorna 0 para esses mercados, a casa simplesmente não oferece essa linha hoje — isso é normal em dias de playoffs. Props de PRA são muito mais comuns.

### `player not found in nba_api: Nome X`

O nome do jogador no Bet365 não bate com o da ESPN. O matching é fuzzy (normaliza unicode, remove pontuação, sufixos Jr/II/III, etc.). Se o log repetir com frequência para um jogador que existe, abra uma issue com o nome exato retornado pela Odds API.

### Quota esgotada (< 10 requests)

O scout para sozinho. Aguarde o mês reiniciar ou faça upgrade na Odds API. Use `--export` para salvar o último resultado e `Ver resultados salvos` no modo interativo para reanalisar sem novas chamadas.

---

## Aviso legal

> Apostas envolvem risco financeiro. EV+ é uma métrica estatística que aponta oportunidades favoráveis no longo prazo — **não é garantia de lucro em nenhuma aposta individual**. Use o Kelly fracionado para limitar exposição. Verifique a legalidade de apostas esportivas na sua jurisdição. Os autores não se responsabilizam por perdas financeiras.
