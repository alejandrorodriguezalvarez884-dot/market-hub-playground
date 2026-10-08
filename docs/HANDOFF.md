# Estado del proyecto y cómo continuar

Última actualización: 2026-10-08. Este documento basta para retomar el trabajo en otra sesión,
sin el historial de la conversación.

## Qué se pidió

El usuario quiere una sección nueva en My Hub, **PlayGround**: un espacio que el usuario configura
a su gusto hablando con un LLM por chat. Va pidiendo visualizaciones y estas aparecen en la
página, con el diseño del portal.

Decisiones del usuario (2026-10-08):
- **Es una tool propia**, con su repo (`market-hub-playground`) y, cuando se despliegue, su
  servicio y su subdominio, como Fundamentals Lab y el Earnings Radar.
- **No está ligada al usuario**: es un lienzo general para componer y visualizar. No lee la
  cartera ni la watchlist del portal.
- **Sin tope de gasto propio**: el límite es el crédito de la cuenta de la API. "Cuando se acaba,
  se acabó."
- Empezar por **un prototipo local**.

Decisiones del agente, avisadas al usuario y a revisar si quiere otras:
- **El modelo compone, no programa.** Devuelve operaciones sobre un tablero de widgets de un
  catálogo cerrado; no genera HTML ni código. Así el diseño es siempre el del portal, las cifras
  salen del código y no hay nada que ejecutar. A cambio, solo se puede pedir lo que el catálogo
  tiene.
- **Modelo: Claude Opus 5.5 con `effort: low`**, como la lectura de Fundamentals Lab
  (`PLAYGROUND_MODEL`, `PLAYGROUND_EFFORT`). Sonnet 5.5 o Haiku 5.5 son más baratos; es una
  variable.
- **El chat contesta siempre en inglés**, escriba el usuario en el idioma que escriba: los textos
  de la web son en inglés y el filtro de consejos solo entiende inglés.
- **Queda un freno por usuario**: 60 turnos de chat por hora y 1.500 peticiones de cifras
  (`CHAT_PER_HOUR`, `DATA_PER_HOUR`). No es un tope de gasto; evita que una página en bucle gaste
  sin que nadie mire.

## Dónde estamos

**Prototipo local hecho y probado (2026-10-08). Sin desplegar. Sin probar con el modelo de
verdad** (no se ha hecho ninguna llamada a Claude: hace falta el permiso del usuario).

- **Qué hace**: una página con el tablero y, al lado (debajo en pantallas estrechas), el chat. El
  usuario escribe lo que quiere ver; el servicio pasa al modelo el tablero, los últimos turnos y la
  petición; el modelo devuelve operaciones (`add`, `update`, `remove`, `move`, `clear`) y una
  frase; el servicio las valida, las aplica y devuelve el tablero nuevo; la página lo pinta y pide
  las cifras de cada widget.
- **Cuatro tipos de widget** (`src/playground/widgets.py`):
  - `price`: un instrumento, velas o línea, volumen, medias de 20, 50 y 200 sesiones; de 1M a 5Y.
  - `compare`: de 2 a 8 instrumentos, la rentabilidad de cada uno desde el mismo día, en líneas
    que salen de cero.
  - `ruler`: de 2 a 20 instrumentos en una misma regla (la de Today del portal), cada uno en su
    rentabilidad del periodo (de 1D a 1Y), ordenados.
  - `table`: de 1 a 20 instrumentos en filas y hasta 8 columnas a elegir entre 18 (precio,
    rentabilidades, volatilidad, distancia al máximo y a las medias, capitalización, PER, PER
    futuro del consenso, dividendo, beta, sector). Se ordena pulsando una cabecera.
  - Todos llevan tamaño (`s` un tercio, `m` la mitad, `l` todo el ancho; por el ancho del tablero,
    no de la ventana) y un título opcional. Hasta 12 widgets.
- **A mano, sin pasar por el chat** (y sin gastar): rango, velas o línea, tamaño, orden y quitar,
  en cada widget; y "Clear the board". Cambiar el tamaño o el orden no vuelve a pedir cifras.
- **Las cifras** (`data.py`): todo sale de las barras diarias de Yahoo (`market.py`, con
  `yfinance`, sin clave; cinco años por símbolo en una petición, dos minutos en memoria). Una
  rentabilidad es el último cierre contra el cierre del que parte el rango, sin dividendos. Las
  seis columnas que no salen de las barras piden la ficha del símbolo (una petición más por
  símbolo, siete días en memoria) y solo cuando la tabla las lleva. Valen acciones y fondos de
  EE. UU., índices (`^GSPC`), futuros (`GC=F`), divisas (`EURUSD=X`) y cripto (`BTC-USD`).
- **El modelo** (`composer.py`): una llamada por turno, con salida estructurada (un esquema
  JSON), las instrucciones en caché y `fallbacks: "default"` (si el modelo rechaza una petición,
  la API la repite en el modelo que recomienda). No ve cifras. Su frase y los títulos pasan el
  filtro de `advice.py` (el vocabulario de `insights.ADVICE` y `watch.TRADE` del portal); si la
  frase no pasa, el chat dice "Done." o "This board shows figures and does not advise.".
  Si la API rechaza la clave o la cuenta se queda sin crédito, el chat se apaga 15 minutos y el
  tablero sigue funcionando a mano. Cada turno deja en el log tokens y coste; nunca lo que
  escribió el usuario ni lo que contestó el modelo.
- **Nada se guarda**: ni tablero, ni conversación, ni usuario. Al recargar la página se pierde
  todo. No hay almacén ni base de datos.
- **Login**: `hubauth.py` es copia del de Fundamentals Lab. Con `HUB_URL` y `HUB_SESSION_SECRET`
  solo entra quien tiene sesión en Market Hub; sin ellas (en local) está abierto.
- **Web** (`site/`, Astro): una página, `index.astro`. `lib/board.ts` lleva el tablero,
  `lib/chat.ts` el chat, `lib/charts.ts` los dos gráficos (Lightweight Charts, sin logo en cada
  gráfico y con el crédito una vez al pie, como la Watchlist del portal) y `lib/views.ts` la regla
  y la tabla. La navegación es la de My Hub, con Playground marcado en "Tools".
- **76 tests en verde**, sin red y sin gasto (`tests/`): las reglas del tablero, las cifras, el
  compositor con una API simulada y el servicio entero. `astro check` y build en verde.
- **Probado en el navegador** (local, cifras de ejemplo y el compositor de pega) a 1440 y 375 px:
  pedir los cuatro tipos por chat, cambiar rango, estilo, tamaño y orden a mano, quitar, un
  símbolo que no existe, una petición sin sentido, la tabla con scroll propio en el móvil, sin
  desbordes ni errores en la consola.
- **Probado contra Yahoo real** desde el equipo Windows (desde Python, no en el navegador): los
  cuatro tipos responden con acciones, índices, futuros, divisas y cripto; la primera petición
  tarda unos 11 s (cargar `yfinance`) y las siguientes alrededor de 1 s.

## Cómo arrancarlo

- `make install` y `make sample`: http://localhost:8080 con cifras inventadas por el código
  (`PLAYGROUND_SAMPLE=1`, marcadas "sample figures") y un compositor de pega
  (`PLAYGROUND_SCRIPTED=1`) que no gasta y entiende cuatro palabras: tickers en mayúsculas,
  "table", "scale", "remove", "clear" y un rango (`chart NVDA 2Y`, `AAPL MSFT YTD`).
- `make serve`: lo mismo con Yahoo real y, si hay `ANTHROPIC_API_KEY` en `.env`, **con el modelo
  de verdad: gasta**.
- En el equipo Windows, desde la raíz del workspace, `.claude/launch.json` tiene
  `playground-sample-windows` (puerto 8086) y `playground-yahoo-windows` (8087: Yahoo real y
  compositor de pega). Antes hay que construir la web (`cd site && npm run build`).
  `uv` necesita ahí `UV_LINK_MODE=copy`, y no hay que lanzarlo desde WSL.

## Siguientes pasos, en orden

1. **Probar con el modelo de verdad**, con permiso del usuario: unas cuantas peticiones en
   lenguaje natural, mirar que el esquema se acepta, qué compone, cuánto tarda y cuánto cuesta
   cada turno (estimado sin medir: entre 1 y 3 céntimos con Opus 5.5). Probar también que
   declina un consejo y una petición fuera del catálogo.
2. Que el usuario lo vea y decida qué falta en el catálogo (más tipos de widget, fundamentales,
   noticias) y si el tablero debe guardarse (`localStorage`, como la Watchlist del portal).
3. Para desplegar, como las otras tools: `Dockerfile`, `scripts/deploy-cloudrun.sh`, el secreto
   de la clave, el subdominio y su mapeo, el enlace "Playground" en `App.astro` del portal y en
   los `HubNav.astro` de `fundamentals-lab` y `decision-signal-lab`, y **decir en `/privacy/`
   del portal que lo que se escribe en el chat va a Anthropic** antes de abrirlo.
4. Registrar el repo como submódulo del workspace `market-hub` y añadirlo a su `CLAUDE.md`.
