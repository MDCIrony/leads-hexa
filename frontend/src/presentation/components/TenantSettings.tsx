import { Building2 } from 'lucide-react';
import type { Tenant, TenantCreate, TenantUpdate } from '../../application/services/tenants.service';
import { TenantForm } from './TenantForm';
import { TenantRow } from './TenantRow';

interface TenantSettingsProps {
  tenants: Tenant[];
  onCreate: (body: TenantCreate) => Promise<Tenant>;
  onUpdate: (id: string, body: TenantUpdate) => Promise<void>;
}

export function TenantSettings({ tenants, onCreate, onUpdate }: TenantSettingsProps) {
  return (
    <div className="space-y-6">
      <TenantForm onCreate={onCreate} />

      <div className="bg-slate-900/40 rounded-xl border border-slate-800 overflow-hidden">
        <div className="p-4 border-b border-slate-800 text-xs font-semibold text-slate-400 uppercase flex items-center justify-between">
          <span>Organizaciones</span>
          <Building2 className="w-4 h-4 text-slate-500" />
        </div>
        <div className="divide-y divide-slate-800">
          {tenants.map((tenant) => (
            <TenantRow key={tenant.id} tenant={tenant} onUpdate={onUpdate} />
          ))}
        </div>
      </div>
    </div>
  );
}
