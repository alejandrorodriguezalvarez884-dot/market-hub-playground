# Instrucciones para agentes

Lee primero [docs/HANDOFF.md](docs/HANDOFF.md): estado, pendientes y siguientes pasos.

Reglas que no se negocian:
- **Nada de trading.** No se escribe código que envíe órdenes ni que se conecte a un broker, y
  no se usa ningún conector de broker (IBKR u otro), ni siquiera para descargar precios.
- **Describir, no recomendar.** Ni la web ni el chat dicen comprar, vender ni mantener, no llaman
  barata o cara a una acción y no predicen precios. Lo que el modelo escribe (su frase y los
  títulos) pasa el filtro de `advice.py`; lo que no pasa no se muestra.
- **El modelo compone, no calcula.** Recibe el tablero, la conversación y la petición, y devuelve
  operaciones sobre el tablero (`widgets.apply`) y una frase. Nunca ve ni escribe una cifra de
  mercado: todo número sale del código (`data.py`). No se ejecuta nada que el modelo escriba.
- **Lo que llega de fuera no se cree.** La respuesta del modelo y el tablero que manda el
  navegador se validan y se rehacen en su única forma (`widgets.normalize`), o se descartan.
- **No se guarda nada del usuario.** El tablero y la conversación viven en la página. Lo que el
  usuario escribe va al modelo y a ningún otro sitio: ni a los logs ni a un almacén. Guardar
  cualquier cosa nueva exige decirlo antes en la página de privacidad del portal.
- **El servicio gasta con la clave del usuario y no tiene tope propio** (decisión suya,
  2026-10-08): el límite es el crédito de la cuenta de la API. No se añaden ni se quitan topes
  sin preguntarle, y antes de una llamada real a Claude se le pide permiso.
- **Nada programado y nada en GitHub Actions.** Todo se lanza a mano desde el `Makefile`.
- **Claves solo en `.env` o en el entorno.** Nunca en el repo, en logs ni en commits, y nunca
  el cuerpo de un error de un proveedor en lo que ve el visitante.

Convenciones:
- Hablar con el usuario en español. Código, comentarios y textos de la web en inglés.
- Python 3.12 con `uv`. Tests con `make test`; web con `make check`.
- Mismo stack y estilo visual que el portal: `site/src/styles/global.css` es copia del de
  `market-hub-landing` (lo propio va al final) y `HubNav.astro` es copia del de `fundamentals-lab`.
- Un tipo de widget nuevo se añade en cuatro sitios: `widgets.py` (qué admite), `data.py` (sus
  cifras), las instrucciones del modelo en `composer.py` y su dibujo en `site/src/lib/`. Con su test.
- Al terminar una tarea relevante, actualizar "Dónde estamos" en `docs/HANDOFF.md`.
