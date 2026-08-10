import { ReactNode } from 'react';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

interface LayoutProps {
  children: ReactNode;
}

// Header and Sidebar read the session themselves now that navigation is
// URL-driven; the tab/tenant props they used to need don't exist anymore.
export function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Header />
      <div className="flex flex-1">
        <Sidebar />
        <main className="flex-1 p-8 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
