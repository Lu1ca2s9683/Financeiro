'use client';

import { useAuth } from '@/contexts/AuthContext';
import { Sidebar } from './Sidebar';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { StoreSelector } from './StoreSelector';
import { Menu, X } from 'lucide-react';

export function MainLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, token } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!loading && !token && pathname !== '/login') {
      router.push('/login');
    }
  }, [loading, token, pathname, router]);

  if (pathname === '/login') {
    return <>{children}</>;
  }

  if (loading) {
    return <div className="flex h-screen items-center justify-center text-slate-400">Carregando...</div>;
  }

  if (!user) return null;

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-40 lg:hidden transition-opacity"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar (Drawer on mobile, Fixed on desktop) */}
      <div className={`
        fixed inset-y-0 left-0 z-50 w-72 bg-slate-900 shadow-xl
        transform transition-transform duration-300 ease-in-out lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <Sidebar onClose={() => setSidebarOpen(false)} />
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 lg:ml-72 transition-all duration-300 ease-in-out h-screen overflow-y-auto">
        {/* Header Mobile & Global */}
        <header className="sticky top-0 z-30 bg-white/90 backdrop-blur-md border-b border-slate-200 px-4 py-3 flex justify-between items-center shadow-sm">
            <div className="flex items-center gap-3 lg:hidden">
              <button
                className="p-2 -ml-2 text-slate-600 hover:bg-slate-100 rounded-lg focus:ring-2 focus:ring-indigo-500 outline-none transition-colors"
                onClick={() => setSidebarOpen(true)}
                aria-label="Abrir menu"
              >
                <Menu size={24} />
              </button>
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
                  <span className="text-white font-bold text-sm">FI</span>
                </div>
                <span className="font-bold text-slate-800 text-lg hidden sm:block">Financeiro</span>
              </div>
            </div>

            <div className="flex items-center gap-4 ml-auto">
              <StoreSelector />
            </div>
        </header>

        {/* Content Body */}
        <main className="flex-1 w-full max-w-[1600px] mx-auto p-4 sm:p-6 lg:p-8">
          {children}
        </main>
      </div>
    </div>
  );
}
