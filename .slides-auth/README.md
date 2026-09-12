# Ingreso con MFA, Google y GitHub

25 diapositivas sobre autenticación, construidas con [Slidev](https://sli.dev).
Carpeta separada de `.slides/`; reutiliza su `node_modules` vía enlace simbólico.

```bash
cd .slides-auth
npm run dev        # http://localhost:3030 — recarga en caliente
npm run build      # genera dist/ (estático)
npm run export     # PDF, requiere playwright-chromium
```

Contenido en `slides.md`. Plantillas en `layouts/` y estilos en `style.css`,
copiados de `.slides/`. Diagramas Mermaid en línea con su `scale` declarado.
