# Migración a microservicios

Diapositivas sobre el desacople de Lead Router en servicios por contexto, construidas con
[Slidev](https://sli.dev). Versión 1: F0–F3 implantadas; las diapositivas de F4 y F5 se completan al
cerrar esas fases. Fuente: `docs/content/microservices/` y ADR-0031–0037.

Carpeta separada de `.slides/`; reutiliza su `node_modules` vía enlace simbólico.

```bash
cd .slides-microservices
npm run dev        # http://localhost:3030 — recarga en caliente
npm run build      # genera dist/ (estático)
npm run export     # PDF, requiere playwright-chromium
```

Contenido en `slides.md`. Plantillas en `layouts/` y estilos en `style.css`, copiados de
`.slides-auth/`. Diagramas Mermaid en línea con su `scale` declarado.
