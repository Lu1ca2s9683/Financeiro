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
    <div className="flex min-h-screen">
      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-slate-900/50 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar - escondida no mobile, fixada e visível em lg */}
      <div className={`fixed inset-y-0 left-0 z-50 transform ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0 transition-transform duration-300 ease-in-out`}>
        <Sidebar />
      </div>

      <div className="flex-1 lg:ml-72 transition-all duration-300 ease-in-out min-w-0">
        {/* Header Global */}
        <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-md border-b border-slate-200 px-4 lg:px-8 py-4 flex justify-between lg:justify-end items-center">
            <button
              className="lg:hidden p-2 text-slate-600 hover:bg-slate-100 rounded-lg"
              onClick={() => setSidebarOpen(!sidebarOpen)}
            >
              {sidebarOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
            <StoreSelector />
        </header>

        {/* Content com overflow escondido horizontalmente para não estourar a tela no mobile */}
        <div className="overflow-x-hidden">
          {children}
        </div>
      </div>
    </div>
  );
}
