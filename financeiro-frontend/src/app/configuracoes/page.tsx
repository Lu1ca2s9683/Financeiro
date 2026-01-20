'use client';

import Link from 'next/link';
import { CreditCard, Tag, Building2, ChevronRight } from 'lucide-react';

export default function ConfiguracoesPage() {
  return (
    <main className="p-8 space-y-8 animate-enter">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Configurações</h1>
        <p className="text-slate-500">Parâmetros gerais do sistema</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm divide-y divide-slate-100">
        
        {/* Item: Categorias */}
        <Link href="/configuracoes/categorias" className="flex items-center justify-between p-6 hover:bg-slate-50 transition-colors group">
          <div className="flex items-center gap-4">
            <div className="p-2 bg-slate-100 rounded-lg text-slate-600 group-hover:bg-indigo-50 group-hover:text-indigo-600 transition-colors">
              <Tag size={20} />
            </div>
            <div>
              <h3 className="font-medium text-slate-900">Categorias de Despesa</h3>
              <p className="text-sm text-slate-500">Gerenciar plano de contas e grupos de custo</p>
            </div>
          </div>
          <ChevronRight size={18} className="text-slate-300 group-hover:text-indigo-400" />
        </Link>

        {/* Item: Taxas de Cartão */}
        <Link href="/configuracoes/taxas" className="flex items-center justify-between p-6 hover:bg-slate-50 transition-colors group">
          <div className="flex items-center gap-4">
            <div className="p-2 bg-slate-100 rounded-lg text-slate-600 group-hover:bg-indigo-50 group-hover:text-indigo-600 transition-colors">
              <CreditCard size={20} />
            </div>
            <div>
              <h3 className="font-medium text-slate-900">Taxas de Cartão</h3>
              <p className="text-sm text-slate-500">Configurar perfis de taxas por bandeira e modalidade</p>
            </div>
          </div>
          <ChevronRight size={18} className="text-slate-300 group-hover:text-indigo-400" />
        </Link>

        {/* Item: Lojas */}
        <div className="flex items-center justify-between p-6 hover:bg-slate-50 transition-colors group cursor-not-allowed opacity-60">
          <div className="flex items-center gap-4">
            <div className="p-2 bg-slate-100 rounded-lg text-slate-600">
              <Building2 size={20} />
            </div>
            <div>
              <h3 className="font-medium text-slate-900">Cadastro de Lojas</h3>
              <p className="text-sm text-slate-500">Sincronizado via API de Vendas (Somente Leitura)</p>
            </div>
          </div>
          <span className="text-xs bg-slate-100 px-2 py-1 rounded text-slate-500 font-medium">Gerenciado Externamente</span>
        </div>

      </div>
    </main>
  );
}