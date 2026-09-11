import { Route, Routes } from 'react-router';
import { AgentsPage } from '../pages/AgentsPage';
import { AssignmentRulesPage } from '../pages/AssignmentRulesPage';
import { BootstrapPage } from '../pages/BootstrapPage';
import { BulkUploadPage } from '../pages/BulkUploadPage';
import { LeadDetailPage } from '../pages/LeadDetailPage';
import { LoginPage } from '../pages/LoginPage';
import { MfaPage } from '../pages/MfaPage';
import { SecurityPage } from '../pages/SecurityPage';
import { MyLeadsPage } from '../pages/MyLeadsPage';
import { NewLeadPage } from '../pages/NewLeadPage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { OrganizationsPage } from '../pages/OrganizationsPage';
import { ScoringRulesPage } from '../pages/ScoringRulesPage';
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
      <Route path="/mfa" element={<MfaPage />} />

      <Route element={<RoleRoute allow={['ADMIN', 'MANAGER', 'AGENT']} />}>
        <Route path="/cuenta/seguridad" element={<SecurityPage />} />
      </Route>

      <Route element={<RoleRoute allow={['ADMIN']} />}>
        <Route path="/admin/organizaciones" element={<OrganizationsPage />} />
      </Route>

      <Route element={<RoleRoute allow={['MANAGER']} />}>
        <Route path="/asesores" element={<AgentsPage />} />
        <Route path="/reglas/puntuacion" element={<ScoringRulesPage />} />
        <Route path="/reglas/asignacion" element={<AssignmentRulesPage />} />
        <Route path="/leads/nuevo" element={<NewLeadPage />} />
        <Route path="/leads/carga" element={<BulkUploadPage />} />
      </Route>

      <Route element={<RoleRoute allow={['AGENT']} />}>
        <Route path="/mis-leads" element={<MyLeadsPage />} />
        <Route path="/mis-leads/:leadId" element={<LeadDetailPage />} />
      </Route>

      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
