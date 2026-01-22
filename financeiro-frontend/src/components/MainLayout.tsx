'use client';

import { useAuth } from '@/contexts/AuthContext';
import { Sidebar } from './Sidebar';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { StoreSelector } from './StoreSelector';

export function MainLayout({ children }: { children: React.ReactNode }) {
  const { user, loading, token } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

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
      <Sidebar />

      <div className="flex-1 ml-72 transition-all duration-300 ease-in-out">
        {/* Header Global */}
        <header className="sticky top-0 z-30 bg-white/80 backdrop-blur-md border-b border-slate-200 px-8 py-4 flex justify-end">
            <StoreSelector />
        </header>

        {children}
      </div>
    </div>
  );
}
