import { Layers, Bell } from 'lucide-react';

interface HeaderProps {
  tenantId: string;
  onTenantChange: (id: string) => void;
}

export function Header({ tenantId, onTenantChange }: HeaderProps) {
  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/50 backdrop-blur px-6 flex items-center justify-between sticky top-0 z-50">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-indigo-600/20 text-indigo-400 rounded-lg border border-indigo-500/30">
          <Layers className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-base font-bold text-slate-100 leading-tight">Lead Router</h1>
          <p className="text-xs text-slate-400">Plataforma Hexagonal Multi-tenant</p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800 text-xs">
          <span className="text-slate-400">Tenant:</span>
          <select
            value={tenantId}
            onChange={(e) => onTenantChange(e.target.value)}
            className="bg-transparent text-slate-200 font-mono focus:outline-none cursor-pointer"
          >
            <option value="b1a2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d">Tenant Alpha (Demo)</option>
            <option value="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d">Tenant Beta</option>
          </select>
        </div>

        <button className="p-2 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors">
          <Bell className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
