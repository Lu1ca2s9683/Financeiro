'use client';

import { useAuth } from '@/contexts/AuthContext';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { FloatingNav } from './FloatingNav';
import { StoreSelector } from './StoreSelector';

export function MainLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, token } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !token && pathname !== '/login' && pathname !== '/landing') {
      router.push('/login');
    }
  }, [loading, token, pathname, router]);

  if (pathname === '/login' || pathname === '/landing') {
    return <>{children}</>;
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center text-slate-400 bg-slate-50 dark:bg-slate-950">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="relative min-h-screen bg-slate-50 dark:bg-slate-950 font-sans selection:bg-indigo-500/30">
      {/* Menu centralizado no topo; seletor de loja ao lado em telas grandes. */}
      <header className="pointer-events-none fixed inset-x-0 top-0 z-50 px-3 pt-3 sm:px-6 sm:pt-4">
        <div className="relative mx-auto flex w-full max-w-[1600px] flex-col items-center gap-2 lg:min-h-16">
          <div className="pointer-events-auto max-w-full">
            <FloatingNav />
          </div>

          <div className="pointer-events-auto self-end rounded-2xl bg-apple-glass px-3 py-2 shadow-[var(--shadow-apple-soft)] transition-shadow duration-300 hover:shadow-[var(--shadow-apple-hover)] lg:absolute lg:right-0 lg:top-0">
            <StoreSelector />
          </div>
        </div>
      </header>

      {/* Reservar altura do cabeçalho para evitar sobreposição ao conteúdo. */}
      <main className="relative z-10 mx-auto w-full max-w-[1600px] px-4 pb-16 pt-44 transition-all duration-500 ease-in-out sm:px-8 sm:pt-40 lg:px-12 lg:pt-28">
        {children}
      </main>
    </div>
  );
}
