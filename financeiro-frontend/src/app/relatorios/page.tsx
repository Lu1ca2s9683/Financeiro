'use client';

import Link from 'next/link';
import { ArrowRight, BarChart3, FileSpreadsheet } from 'lucide-react';

export default function RelatoriosPage() {
  return (
    <main className="p-8 space-y-8 animate-enter">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Relatórios Financeiros</h1>
          <p className="text-slate-500">Extração e análise de dados consolidados</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Card DRE */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-all group cursor-pointer">
          <div className="p-3 bg-indigo-50 text-indigo-600 rounded-lg w-fit mb-4 group-hover:bg-indigo-100 transition-colors">
            <BarChart3 size={24} />
          </div>
          <h3 className="font-bold text-lg text-slate-800 mb-2">DRE Gerencial</h3>
          <p className="text-slate-500 text-sm mb-6">
            Demonstrativo do Resultado do Exercício em regime de caixa, com composição dos recebimentos e visão vertical.
          </p>
          <Link href="/relatorios/dre" className="w-full py-2 border border-slate-200 rounded-lg text-slate-600 font-medium hover:bg-slate-50 flex items-center justify-center gap-2">
            <span>Abrir DRE</span> <ArrowRight size={16} />
          </Link>
        </div>

        {/* Card Extrato */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-all group cursor-pointer">
          <div className="p-3 bg-emerald-50 text-emerald-600 rounded-lg w-fit mb-4 group-hover:bg-emerald-100 transition-colors">
            <FileSpreadsheet size={24} />
          </div>
          <h3 className="font-bold text-lg text-slate-800 mb-2">Extrato de Despesas</h3>
          <p className="text-slate-500 text-sm mb-6">
            Listagem analítica das contas a pagar, com classificação por categoria e identificação de fornecedor.
          </p>
          <Link href="/despesas" className="w-full py-2 border border-slate-200 rounded-lg text-slate-600 font-medium hover:bg-slate-50 flex items-center justify-center gap-2">
            <span>Consultar despesas</span> <ArrowRight size={16} />
          </Link>
        </div>
      </div>
    </main>
  );
}
