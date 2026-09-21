# UML Diagrams — BrandShield AI

Generated from the actual source code in `backend/app/`. The object diagram uses a real
snapshot of the running system (9,984 analysed mentions, YouTube channel @cristiano).

## Files

| File | Use |
|---|---|
| `01-class-diagram.png/.svg` | Full class diagram — 28 classes (tall; best for the report) |
| `01a-class-core-pipeline.png/.svg` | Part 1 for slides: App, storage, message bus, NLP pipeline |
| `01b-class-sources-analytics.png/.svg` | Part 2 for slides: collectors, services, analytics, entities |
| `04-class-diagram-social-integrations.png/.svg` | Class diagram focused on the YouTube and Instagram integrations (collectors, services, entities, external APIs) |
| `02-object-diagram.png/.svg` | Runtime snapshot with real values |
| `03-component-diagram.png/.svg` | Component view, vertical layout (fits a slide) |
| `03-component-diagram-wide.png/.svg` | Same diagram, horizontal (good for a poster or handout) |
| `uml-diagrams.html` | All diagrams in one page, opens in any browser |
| `*.mmd` | Mermaid source — edit these, then re-render |

PNGs are rendered at 2x resolution, so they stay sharp when projected.
SVGs are vector — use these in PowerPoint if you want to resize without blur.

## Editing a diagram

1. Open the `.mmd` file and change it.
2. Paste the contents into https://mermaid.live to preview, or re-render locally.
3. In mermaid.live: **Actions → PNG / SVG** to export.

## Notation used

- `*--` composition (owner creates and destroys the part)
- `o--` aggregation (references, independent lifetime)
- `<|--` generalization (inheritance)
- `<|..` realization (implements an interface)
- `..>` dependency (uses or creates)
- `<<interface>>` / `<<utility>>` stereotypes
