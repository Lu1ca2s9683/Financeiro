'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard, FileText, Settings, PieChart,
  Wallet, LogOut
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { cn } from '@/lib/utils';

export function FloatingNav() {
  const pathname = usePathname();
  const { logout } = useAuth();

  const menuItems = [
    { icon: LayoutDashboard, label: 'Geral', href: '/' },
    { icon: Wallet, label: 'Tesouraria', href: '/tesouraria' },
    { icon: FileText, label: 'Despesas', href: '/despesas' },
    { icon: PieChart, label: 'DRE', href: '/relatorios/dre' },
    { icon: Settings, label: 'Conferência', href: '/relatorios/conferencia' },
  ];

  return (
    <nav className="apple-floating-nav flex items-center gap-1.5 p-2 rounded-full bg-apple-glass shadow-[var(--shadow-apple-dark)] border border-slate-200/50 dark:border-slate-800/50 backdrop-blur-2xl transition-all duration-300">
      {menuItems.map((item) => {
        const isActive = pathname === item.href;
        const Icon = item.icon;

        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "group relative flex items-center justify-center w-12 h-12 rounded-full transition-all duration-300 ease-out outline-none focus-visible:ring-2 focus-visible:ring-indigo-500",
              isActive
                ? "bg-indigo-600 shadow-md text-white scale-105"
                : "text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white hover:bg-slate-100/50 dark:hover:bg-slate-800/50"
            )}
            title={item.label}
          >
            <Icon
              size={22}
              strokeWidth={isActive ? 2.5 : 2}
              className={cn(
                "transition-transform duration-300",
                isActive ? "scale-100" : "group-hover:scale-110 group-active:scale-95"
              )}
            />

            {/* Tooltip on Hover */}
            <span className="absolute -top-10 scale-0 transition-all rounded bg-slate-900 dark:bg-white text-white dark:text-slate-900 p-2 text-xs font-medium group-hover:scale-100 shadow-[var(--shadow-apple-soft)] pointer-events-none origin-bottom">
              {item.label}
            </span>
          </Link>
        );
      })}

      <div className="w-[1px] h-8 bg-slate-300/50 dark:bg-slate-700/50 mx-1"></div>

      <button
        onClick={logout}
        className="group relative flex items-center justify-center w-12 h-12 rounded-full text-rose-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-500/10 transition-all duration-300 ease-out outline-none focus-visible:ring-2 focus-visible:ring-rose-500"
        title="Sair"
      >
        <LogOut size={22} strokeWidth={2} className="group-hover:scale-110 group-active:scale-95 transition-transform duration-300" />
        <span className="absolute -top-10 scale-0 transition-all rounded bg-rose-600 text-white p-2 text-xs font-medium group-hover:scale-100 shadow-[var(--shadow-apple-soft)] pointer-events-none origin-bottom">
          Sair
        </span>
      </button>
    </nav>
  );
}
