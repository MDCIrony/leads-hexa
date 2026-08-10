import { Route, Routes } from 'react-router';
import { AgentsPage } from '../pages/AgentsPage';
import { BootstrapPage } from '../pages/BootstrapPage';
import { LeadDetailPage } from '../pages/LeadDetailPage';
import { LoginPage } from '../pages/LoginPage';
import { MyLeadsPage } from '../pages/MyLeadsPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { OrganizationsPage } from '../pages/OrganizationsPage';
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
      <Route path="/bootstrap" element={<BootstrapPage />} />
      <Route path="/login" element={<LoginPage />} />

      <Route element={<RoleRoute allow={['ADMIN']} />}>
        <Route path="/admin/organizaciones" element={<OrganizationsPage />} />
      </Route>

      <Route element={<RoleRoute allow={['MANAGER']} />}>
        <Route path="/asesores" element={<AgentsPage />} />
        <Route path="/reglas/puntuacion" element={<PlaceholderPage title="Reglas de puntuación" />} />
        <Route path="/reglas/asignacion" element={<PlaceholderPage title="Reglas de asignación" />} />
        <Route path="/leads/nuevo" element={<PlaceholderPage title="Alta de lead" />} />
        <Route path="/leads/carga" element={<PlaceholderPage title="Carga masiva" />} />
      </Route>

      <Route element={<RoleRoute allow={['AGENT']} />}>
        <Route path="/mis-leads" element={<MyLeadsPage />} />
        <Route path="/mis-leads/:leadId" element={<LeadDetailPage />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
