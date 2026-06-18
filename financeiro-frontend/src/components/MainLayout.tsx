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
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="relative min-h-screen bg-slate-50 dark:bg-slate-950 font-sans selection:bg-indigo-500/30">

      {/* Floating Top Header (Optional, for global actions like StoreSelector) */}
      <header className="fixed top-0 left-0 right-0 z-40 px-6 py-4 pointer-events-none flex justify-end">
        <div className="pointer-events-auto bg-apple-glass rounded-2xl shadow-[var(--shadow-apple-soft)] px-3 py-2 flex items-center gap-4 transition-all hover:shadow-[var(--shadow-apple-hover)]">
          <StoreSelector />
        </div>
      </header>

      {/* Main Content Area: scrolls freely below the floating nav */}
      <main className="relative z-10 w-full max-w-[1600px] mx-auto pb-32 pt-20 px-4 sm:px-8 lg:px-12 transition-all duration-500 ease-in-out">
        {children}
      </main>

      {/* Apple-style Floating Dock Navigation */}
      <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 pointer-events-none">
         <div className="pointer-events-auto">
            <FloatingNav />
         </div>
      </div>
    </div>
  );
}
