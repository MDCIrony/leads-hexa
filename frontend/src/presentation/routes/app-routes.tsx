import { Route, Routes } from 'react-router';
import { AgentsPage } from '../pages/AgentsPage';
import { LoginPage } from '../pages/LoginPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { PlaceholderPage } from '../pages/PlaceholderPage';
import { RoleRoute } from './role-guard';
import { RootRedirect } from './root-redirect';

/**
 * The full route map for the app: every screen has its own URL, is gated by
 * role where it needs to be, and survives a pasted URL or the back button.
 * Screens not built yet render a placeholder until their view lands.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/bootstrap" element={<PlaceholderPage title="Arranque de la plataforma" />} />
      <Route path="/login" element={<LoginPage />} />

      <Route element={<RoleRoute allow={['ADMIN']} />}>
        <Route path="/admin/organizaciones" element={<PlaceholderPage title="Organizaciones" />} />
      </Route>

      <Route element={<RoleRoute allow={['MANAGER']} />}>
        <Route path="/asesores" element={<AgentsPage />} />
        <Route path="/reglas/puntuacion" element={<PlaceholderPage title="Reglas de puntuación" />} />
        <Route path="/reglas/asignacion" element={<PlaceholderPage title="Reglas de asignación" />} />
        <Route path="/leads/nuevo" element={<PlaceholderPage title="Alta de lead" />} />
        <Route path="/leads/carga" element={<PlaceholderPage title="Carga masiva" />} />
      </Route>

      <Route element={<RoleRoute allow={['AGENT']} />}>
        <Route path="/mis-leads" element={<PlaceholderPage title="Mis leads" />} />
        <Route path="/mis-leads/:leadId" element={<PlaceholderPage title="Detalle del lead" />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
