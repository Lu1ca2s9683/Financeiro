'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, FileText, Settings, PieChart, DollarSign, ChevronRight } from 'lucide-react';

const menuItems = [
  { icon: LayoutDashboard, label: 'Visão Geral', href: '/' },
  { icon: FileText, label: 'Contas a Pagar', href: '/despesas' },
  { icon: PieChart, label: 'Relatórios', href: '/relatorios' }, 
  { icon: Settings, label: 'Configurações', href: '/configuracoes' },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-72 bg-slate-900 text-slate-300 min-h-screen fixed left-0 top-0 flex flex-col shadow-xl z-50">
      {/* Logo Area */}
      <div className="p-8 border-b border-slate-800/50 flex items-center gap-3 bg-slate-900/50 backdrop-blur-sm">
        <div className="bg-gradient-to-br from-indigo-500 to-indigo-700 p-2.5 rounded-xl shadow-lg shadow-indigo-900/20">
           <DollarSign className="text-white" size={22} strokeWidth={2.5} />
        </div>
        <div>
          <h1 className="font-bold text-white text-lg tracking-tight leading-tight">Financeiro</h1>
          <span className="text-xs text-indigo-400 font-medium uppercase tracking-wider">Enterprise</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1 mt-4">
        <p className="px-4 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Principal</p>
        {menuItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`group flex items-center justify-between px-4 py-3.5 rounded-xl transition-all duration-200 ${
                isActive 
                  ? 'bg-indigo-600/10 text-indigo-400 font-medium ring-1 ring-indigo-500/20' 
                  : 'hover:bg-slate-800/50 hover:text-white text-slate-400'
              }`}
            >
              <div className="flex items-center gap-3">
                <item.icon size={20} className={`transition-colors ${isActive ? 'text-indigo-400' : 'text-slate-500 group-hover:text-white'}`} />
                <span>{item.label}</span>
              </div>
              {isActive && <ChevronRight size={16} className="text-indigo-500 animate-in fade-in slide-in-from-left-1" />}
            </Link>
          );
        })}
      </nav>

      {/* Footer / User Info */}
      <div className="p-4 border-t border-slate-800/50 bg-slate-900/30">
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 flex items-center gap-3 shadow-inner">
          <div className="w-10 h-10 rounded-full bg-indigo-500 flex items-center justify-center text-white font-bold text-sm shadow-md">
            LM
          </div>
          <div className="overflow-hidden">
            <p className="text-sm font-semibold text-white truncate">Loja Matriz</p>
            <p className="text-xs text-slate-400 truncate">ID: 001 • Ativo</p>
          </div>
        </div>
      </div>
    </aside>
  );
}