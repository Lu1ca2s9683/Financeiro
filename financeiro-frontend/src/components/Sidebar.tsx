'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  LayoutDashboard, FileText, Settings, PieChart, 
  DollarSign, ChevronRight, ChevronLeft, Wallet, LogOut, X 
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

interface SidebarProps {
  onClose?: () => void;
}

export function Sidebar({ onClose }: SidebarProps) {
  const pathname = usePathname();
  const { logout, activeLoja } = useAuth();
  
  // Estado que controla se o menu está retraído ou expandido (apenas para Desktop)
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Aqui você pode alterar facilmente as palavras do menu (propriedade 'label')
  const menuItems = [
    { icon: LayoutDashboard, label: 'Visão Geral', href: '/' },
    { icon: Wallet, label: 'Tesouraria', href: '/tesouraria' },
    { icon: FileText, label: 'Contas a Pagar', href: '/despesas' },
    { icon: PieChart, label: 'Relatórios', href: '/relatorios' }, 
    { icon: Settings, label: 'Configurações', href: '/configuracoes' },
  ];

  return (
    <aside 
      className={`bg-slate-900 text-slate-300 min-h-screen flex flex-col z-50 h-full relative transition-all duration-300 ease-in-out ${
        isCollapsed ? 'w-20' : 'w-72'
      }`}
    >
      {/* Botão de Toggle (Visível apenas em telas grandes) */}
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="absolute -right-3 top-10 bg-indigo-600 rounded-full p-1.5 text-white hover:bg-indigo-500 shadow-lg hidden lg:flex items-center justify-center border border-indigo-400/30 transition-transform hover:scale-110 z-50"
      >
        {isCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>

      {/* Logo Area */}
      <div className={`p-6 border-b border-slate-800/50 flex items-center bg-slate-900/50 backdrop-blur-sm transition-all duration-300 ${isCollapsed ? 'justify-center px-0' : 'justify-between'}`}>
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="bg-gradient-to-br from-indigo-500 to-indigo-700 p-2.5 rounded-xl shadow-lg shadow-indigo-900/20 shrink-0">
             <DollarSign className="text-white" size={22} strokeWidth={2.5} />
          </div>
          
          <div className={`transition-all duration-300 whitespace-nowrap ${isCollapsed ? 'opacity-0 w-0' : 'opacity-100 w-auto'}`}>
            <h1 className="font-bold text-white text-lg tracking-tight leading-tight">Financeiro</h1>
            <span className="text-xs text-indigo-400 font-medium uppercase tracking-wider">Enterprise</span>
          </div>
        </div>

        {/* Botão X para fechar no Mobile */}
        {onClose && !isCollapsed && (
           <button onClick={onClose} className="lg:hidden p-2 rounded-md hover:bg-slate-800 text-slate-400 transition-colors shrink-0">
             <X size={20} />
           </button>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1 mt-4 overflow-y-auto overflow-x-hidden no-scrollbar">
        <p className={`px-4 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2 transition-all duration-300 whitespace-nowrap ${isCollapsed ? 'opacity-0 h-0 m-0' : 'opacity-100'}`}>
          Principal
        </p>
        
        {menuItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              title={isCollapsed ? item.label : undefined}
              className={`group flex items-center px-3 py-3.5 rounded-xl transition-all duration-200 ${
                isActive 
                  ? 'bg-indigo-600/10 text-indigo-400 font-medium ring-1 ring-indigo-500/20' 
                  : 'hover:bg-slate-800/50 hover:text-white text-slate-400'
              } ${isCollapsed ? 'justify-center' : 'justify-between'}`}
            >
              <div className="flex items-center gap-3">
                <item.icon size={20} className={`shrink-0 transition-colors ${isActive ? 'text-indigo-400' : 'text-slate-500 group-hover:text-white'}`} />
                <span className={`transition-all duration-300 whitespace-nowrap ${isCollapsed ? 'opacity-0 w-0 hidden' : 'opacity-100 w-auto block'}`}>
                  {item.label}
                </span>
              </div>
              
              {!isCollapsed && isActive && (
                <ChevronRight size={16} className="text-indigo-500 shrink-0 animate-in fade-in slide-in-from-left-1" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* Footer / User Info */}
      <div className={`p-4 border-t border-slate-800/50 bg-slate-900/30 flex flex-col gap-3 transition-all duration-300 ${isCollapsed ? 'items-center' : ''}`}>
        
        <div className={`bg-slate-800/50 rounded-xl p-3 border border-slate-700/50 flex items-center gap-3 shadow-inner overflow-hidden ${isCollapsed ? 'justify-center w-12' : 'w-full'}`}>
          <div className="w-9 h-9 rounded-full bg-indigo-500 flex shrink-0 items-center justify-center text-white font-bold text-sm shadow-md">
            {activeLoja?.nome?.substring(0, 2).toUpperCase() || 'LJ'}
          </div>
          <div className={`transition-all duration-300 min-w-0 whitespace-nowrap ${isCollapsed ? 'opacity-0 w-0 hidden' : 'opacity-100 w-auto block'}`}>
            <p className="text-sm font-semibold text-white truncate" title={activeLoja?.nome || 'Loja Indefinida'}>
              {activeLoja?.nome || 'Loja Indefinida'}
            </p>
            <p className="text-xs text-slate-400 truncate">ID: {activeLoja?.id || '000'} • Ativo</p>
          </div>
        </div>

        <button
          title={isCollapsed ? "Sair" : undefined}
          onClick={() => {
            if(onClose) onClose();
            logout();
          }}
          className={`flex items-center justify-center gap-2 rounded-lg bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 hover:text-rose-300 transition-colors font-medium text-sm border border-rose-500/20 shrink-0 ${isCollapsed ? 'w-12 h-10 p-0' : 'w-full py-2.5'}`}
        >
          <LogOut size={16} className="shrink-0" /> 
          <span className={`transition-all duration-300 whitespace-nowrap ${isCollapsed ? 'opacity-0 w-0 hidden' : 'opacity-100 w-auto block'}`}>
            Sair
          </span>
        </button>

      </div>
    </aside>
  );
}
          </div>
        </div>
        {onClose && (
           <button onClick={onClose} className="lg:hidden p-2 rounded-md hover:bg-slate-800 text-slate-400 transition-colors">
             <X size={20} />
           </button>
        )}
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
      <div className="p-4 border-t border-slate-800/50 bg-slate-900/30 flex flex-col gap-3">
        <div className="bg-slate-800/50 rounded-xl p-4 border border-slate-700/50 flex items-center gap-3 shadow-inner">
          <div className="w-10 h-10 rounded-full bg-indigo-500 flex shrink-0 items-center justify-center text-white font-bold text-sm shadow-md">
            {activeLoja?.nome?.substring(0, 2).toUpperCase() || 'LJ'}
          </div>
          <div className="overflow-hidden min-w-0">
            <p className="text-sm font-semibold text-white truncate" title={activeLoja?.nome || 'Loja Indefinida'}>
              {activeLoja?.nome || 'Loja Indefinida'}
            </p>
            <p className="text-xs text-slate-400 truncate">ID: {activeLoja?.id || '000'} • Ativo</p>
          </div>
        </div>

        <button
          onClick={() => {
            if(onClose) onClose();
            logout();
          }}
          className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 hover:text-rose-300 transition-colors font-medium text-sm border border-rose-500/20"
        >
          <LogOut size={16} /> Sair
        </button>
      </div>
    </aside>
  );
}
