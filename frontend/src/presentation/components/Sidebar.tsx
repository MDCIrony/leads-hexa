import { LayoutDashboard, Sliders, UploadCloud, Users } from 'lucide-react';

export type TabType = 'dashboard' | 'rules' | 'upload' | 'settings';

interface SidebarProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
}

export function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard Leads', icon: LayoutDashboard },
    { id: 'rules', label: 'Reglas de Scoring', icon: Sliders },
    { id: 'upload', label: 'Carga Masiva (CSV)', icon: UploadCloud },
    { id: 'settings', label: 'Agentes & Webhooks', icon: Users },
  ] as const;

  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-900/30 p-4 flex flex-col gap-2">
      <div className="px-3 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
        Navegación
      </div>

      {menuItems.map((item) => {
        const Icon = item.icon;
        const isActive = activeTab === item.id;
        return (
          <button
            key={item.id}
            onClick={() => onTabChange(item.id as TabType)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
              isActive
                ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
            }`}
          >
            <Icon className="w-4 h-4" />
            <span>{item.label}</span>
          </button>
        );
      })}
    </aside>
  );
}
