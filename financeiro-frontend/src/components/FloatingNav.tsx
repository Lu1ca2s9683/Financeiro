'use client';

import type { PointerEvent as ReactPointerEvent } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard, FileText, Settings, PieChart,
  Wallet, LogOut
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { cn } from '@/lib/utils';
import './dock-nav.css';

const menuItems = [
  { icon: LayoutDashboard, label: 'Geral', href: '/' },
  { icon: Wallet, label: 'Tesouraria', href: '/tesouraria' },
  { icon: FileText, label: 'Despesas', href: '/despesas' },
  { icon: PieChart, label: 'DRE', href: '/relatorios/dre' },
  { icon: Settings, label: 'Conferência', href: '/relatorios/conferencia' },
  { icon: Settings, label: 'Configurações', href: '/configuracoes' },
];

// Usar CSS variables evita renderizações do React a cada movimento do mouse.
function handleDockPointerMove(event: ReactPointerEvent<HTMLElement>) {
  if (event.pointerType !== 'mouse') return;
  const bounds = event.currentTarget.getBoundingClientRect();
  event.currentTarget.style.setProperty('--dock-x', `${event.clientX - bounds.left}px`);
  event.currentTarget.style.setProperty('--dock-y', `${event.clientY - bounds.top}px`);
}

function handleMagneticMove(event: ReactPointerEvent<HTMLElement>) {
  if (event.pointerType !== 'mouse') return;
  const bounds = event.currentTarget.getBoundingClientRect();
  event.currentTarget.style.setProperty('--magnetic-x', `${(((event.clientX - bounds.left) / bounds.width) - 0.5) * 7}px`);
  event.currentTarget.style.setProperty('--magnetic-y', `${(((event.clientY - bounds.top) / bounds.height) - 0.5) * 7}px`);
}

function resetMagnetic(event: ReactPointerEvent<HTMLElement>) {
  event.currentTarget.style.removeProperty('--magnetic-x');
  event.currentTarget.style.removeProperty('--magnetic-y');
}

const tooltipClasses = 'dock-tooltip pointer-events-none absolute left-1/2 top-full z-20 mt-3 -translate-x-1/2 whitespace-nowrap rounded-lg bg-slate-900 px-2.5 py-1.5 text-xs font-medium text-white shadow-lg dark:bg-white dark:text-slate-900';

export function FloatingNav() {
  const pathname = usePathname();
  const { logout } = useAuth();

  return (
    <nav
      aria-label="Navegação principal"
      onPointerMove={handleDockPointerMove}
      className="top-floating-nav relative isolate flex max-w-full items-center gap-0.5 rounded-full border border-slate-200/50 bg-apple-glass p-1.5 shadow-[var(--shadow-apple-dark)] backdrop-blur-2xl sm:gap-1.5 sm:p-2 dark:border-slate-800/50"
    >
      {menuItems.map((item) => {
        const isActive = item.href === '/'
          ? pathname === '/'
          : pathname === item.href || pathname.startsWith(`${item.href}/`);
        const Icon = item.icon;

        return (
          <Link
            key={item.href}
            href={item.href}
            aria-label={item.label}
            aria-current={isActive ? 'page' : undefined}
            onPointerMove={handleMagneticMove}
            onPointerLeave={resetMagnetic}
            className={cn(
              'dock-nav-item group relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full outline-none transition-[background-color,box-shadow,color] duration-300 focus-visible:ring-2 focus-visible:ring-indigo-500 min-[400px]:h-11 min-[400px]:w-11 sm:h-12 sm:w-12',
              isActive
                ? 'bg-indigo-600 text-white shadow-md'
                : 'text-slate-500 hover:bg-slate-100/70 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-800/60 dark:hover:text-white'
            )}
          >
            <Icon size={21} strokeWidth={isActive ? 2.5 : 2} className="dock-nav-icon" />
            <span aria-hidden="true" className={tooltipClasses}>{item.label}</span>
          </Link>
        );
      })}

      <div aria-hidden="true" className="mx-0.5 h-7 w-px shrink-0 bg-slate-300/50 sm:mx-1 sm:h-8 dark:bg-slate-700/50" />

      <button
        type="button"
        onClick={logout}
        onPointerMove={handleMagneticMove}
        onPointerLeave={resetMagnetic}
        className="dock-nav-item group relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-rose-500 outline-none transition-colors duration-300 hover:bg-rose-50 hover:text-rose-600 focus-visible:ring-2 focus-visible:ring-rose-500 min-[400px]:h-11 min-[400px]:w-11 sm:h-12 sm:w-12 dark:hover:bg-rose-500/10"
        aria-label="Sair"
      >
        <LogOut size={21} strokeWidth={2} className="dock-nav-icon" />
        <span aria-hidden="true" className={tooltipClasses}>Sair</span>
      </button>
    </nav>
  );
}
