import { ReactNode } from 'react';
import { Header } from './Header';
import { Sidebar, TabType } from './Sidebar';

interface LayoutProps {
  tenantId: string;
  onTenantChange: (id: string) => void;
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
  children: ReactNode;
}

export function Layout({ tenantId, onTenantChange, activeTab, onTabChange, children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Header tenantId={tenantId} onTenantChange={onTenantChange} />
      <div className="flex flex-1">
        <Sidebar activeTab={activeTab} onTabChange={onTabChange} />
        <main className="flex-1 p-8 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
