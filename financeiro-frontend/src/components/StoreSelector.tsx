'use client';

import { useAuth } from '@/contexts/AuthContext';
import { Store, ChevronDown, Check, Building2, UserCircle } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';

export function StoreSelector() {
  const { user, grupos, activeLoja, switchStore, logout } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  if (!user || !activeLoja) return null;

  return (
    <div className="relative" ref={menuRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-3 pl-3 pr-4 py-2 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors border border-slate-200"
      >
        <div className="w-8 h-8 bg-white rounded-lg flex items-center justify-center text-indigo-600 shadow-sm">
          <Store size={18} />
        </div>
        <div className="text-left hidden sm:block">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider leading-none mb-0.5">Loja Ativa</p>
          <p className="text-sm font-bold text-slate-800 leading-none truncate max-w-[140px]">{activeLoja.nome}</p>
        </div>
        <ChevronDown size={16} className={`text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute top-full right-0 mt-2 w-80 bg-white rounded-2xl shadow-xl border border-slate-100 overflow-hidden z-50 animate-in fade-in zoom-in-95 duration-100">

          {/* User Info Header */}
          <div className="p-4 bg-slate-50 border-b border-slate-100 flex items-center gap-3">
            <div className="w-10 h-10 bg-indigo-100 rounded-full flex items-center justify-center text-indigo-600">
              <UserCircle size={24} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-bold text-slate-900 truncate">{user.nome}</p>
              <p className="text-xs text-slate-500 truncate">{user.email}</p>
            </div>
          </div>

          <div className="max-h-[300px] overflow-y-auto p-2">
            {grupos.map((grupo) => (
              <div key={grupo.id} className="mb-2 last:mb-0">
                <div className="px-3 py-1.5 flex items-center gap-2">
                  <Building2 size={12} className="text-slate-400" />
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">{grupo.nome}</span>
                </div>

                <div className="space-y-1">
                  {grupo.lojas.map((loja) => {
                    const isActive = loja.id === activeLoja.id;
                    return (
                      <button
                        key={loja.id}
                        onClick={() => {
                          if (!isActive) {
                            switchStore(loja.id);
                            setIsOpen(false);
                          }
                        }}
                        className={`
                          w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-sm transition-all
                          ${isActive
                            ? 'bg-indigo-50 text-indigo-700 font-medium'
                            : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                          }
                        `}
                      >
                        <span className="truncate">{loja.nome}</span>
                        {isActive && <Check size={16} className="text-indigo-600" />}
                        {!isActive && <span className="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded text-slate-400 border border-slate-200">{loja.role}</span>}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>

          <div className="p-2 border-t border-slate-100 bg-slate-50">
            <button
              onClick={() => logout()}
              className="w-full text-center text-sm text-rose-600 font-medium py-2 hover:bg-rose-50 rounded-lg transition-colors"
            >
              Sair do Sistema
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
