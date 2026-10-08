# Playground

**Un tablero de mercado que se compone pidiéndolo.** El usuario escribe lo que quiere ver ("compara
Apple, Microsoft y Alphabet este año") y la vista aparece en su tablero, con el diseño de
[Market Hub](https://themarkethub.app). Después la ajusta a mano: rango, tamaño, orden.

- **Cuatro vistas**: gráfico de precio, comparativa de rentabilidades, varios valores en una misma
  regla y tabla de cifras.
- **El modelo compone, no calcula**: Claude elige vistas y tickers; todas las cifras salen del
  código, a partir de las barras diarias de Yahoo Finance.
- **Describe, no recomienda**: ni la web ni el chat aconsejan ni predicen.
- **No guarda nada**: el tablero y la conversación viven en la página.

Es una herramienta de Market Hub, con el mismo stack que las demás: FastAPI (`src/playground/`) y
Astro (`site/`). Estado: prototipo local.

```bash
make install
make sample   # http://localhost:8080, con cifras de ejemplo y sin gastar
```

El estado, las decisiones y los siguientes pasos están en [docs/HANDOFF.md](docs/HANDOFF.md).
