# STEP 06: Componentes UI y Vistas React 19 + Tailwind (Frontend)

## 🎯 Objetivo
Desarrollar la interfaz de usuario SPA responsiva y moderna en React 19 con estilos exclusivamente en Tailwind CSS, estructurada según las vistas especificadas en el requerimiento.

---

## 🏗️ Componentes a Desarrollar (`frontend/src/presentation/`)

### 1. Dashboard de Leads (`presentation/pages/DashboardPage.tsx`)
- **Tabla de Leads**: Muestra listado de prospectos con badge de estado (`NEW`, `QUALIFIED`, `DISQUALIFIED`, `ASSIGNED`, `FAILED`), puntaje del score y agente asignado.
- **Filtros y Búsqueda**: Filtro selector por estado y barra de búsqueda por email/empresa.
- **Drawer / Modal de Desglose**: Modal interactivo para inspeccionar el historial y desglose de reglas de scoring aplicadas a un lead seleccionado.

### 2. Constructor de Reglas de Scoring (`presentation/pages/RuleBuilderPage.tsx`)
- **Formulario Interactivo**: Tipo "If [Field] [Operator] [Value] Then Add [Score Delta]".
- **Lista de Reglas Configuradas**: Reordenamiento, switch de activación/desactivación y prueba de reglas en vivo con un simulador JSON.

### 3. Asistente de Carga Masiva (`presentation/pages/BulkUploadPage.tsx`)
- **Drag-and-Drop File Uploader**: Soporte de archivos `.csv` y `.xlsx`.
- **Pre-visualización de Filas**: Tabla con las primeras 5 filas del archivo subido.
- **Mapeo Dinámico de Columnas**: Dropdowns para vincular las columnas del archivo a los campos esperados por la plataforma.

### 4. Configuración de Agentes y Webhooks (`presentation/pages/SettingsPage.tsx`)
- **Gestión de Agentes de Ventas**: Crear/editar agentes, asignación de equipo y switch Activo/Inactivo.
- **Configuración de Webhooks Salientes**: Configuración de URL objetivo y Secret Token con botón para "Enviar Payload de Prueba".

---

## 🧪 Protocolo de Verificación TDD y Validaciones (3 Pasos)

### Paso 1: Pruebas Unitarias de Componentes UI (React Testing Library + Vitest)
- Crear tests unitarios en `frontend/tests/unit/components/`:
  - `DashboardTable.test.tsx`: Renderizado correcto de lista de leads y formateo de badges de estado.
  - `RuleBuilderForm.test.tsx`: Emisión correcta del evento de creación de regla con los campos seleccionados.
  - `BulkUploader.test.tsx`: Simulación de subida de archivo y previsualización de 5 filas.

Comando de ejecución:
```bash
cd frontend && npm run test
```

### Paso 2: Revisión de Consistencia Estilística y Arquitectura
- Confirmar que NO EXISTAN archivos `.css` adicionales ni estilos inline (`style={{...}}`); toda la presentación debe usar clases de Tailwind CSS.
- Verificar el uso exclusivo de React 19 hooks estándar y desacoplamiento mediante Custom Hooks de aplicación (`useLeads`, `useRules`, `useAgents`).

### Paso 3: Verificación de Integración Visual
- Probar la ejecución en servidor dev (`npm run dev`) para asegurar respuesta fluida de la UI, animaciones de micro-interacción y layouts responsivos.
