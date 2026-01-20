'use client';

import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react';
import { useFinanceiro } from '@/contexts/FinanceiroContext';

export function PeriodSelector() {
  const { mes, setMes, ano, setAno, periodoFormatado } = useFinanceiro();

  const handlePreviousMonth = () => {
    if (mes === 1) {
      setMes(12);
      setAno(ano - 1);
    } else {
      setMes(mes - 1);
    }
  };

  const handleNextMonth = () => {
    if (mes === 12) {
      setMes(1);
      setAno(ano + 1);
    } else {
      setMes(mes + 1);
    }
  };

  return (
    <div className="flex items-center bg-white border border-slate-200 rounded-lg shadow-sm p-1">
      <button 
        onClick={handlePreviousMonth}
        className="p-2 hover:bg-slate-50 text-slate-500 hover:text-indigo-600 rounded-md transition-colors"
        title="Mês Anterior"
      >
        <ChevronLeft size={20} />
      </button>

      <div className="flex items-center gap-2 px-4 min-w-[180px] justify-center border-x border-slate-100">
        <Calendar size={16} className="text-indigo-500" />
        <span className="font-semibold text-slate-700 capitalize text-sm md:text-base">
          {periodoFormatado}
        </span>
      </div>

      <button 
        onClick={handleNextMonth}
        className="p-2 hover:bg-slate-50 text-slate-500 hover:text-indigo-600 rounded-md transition-colors"
        title="Próximo Mês"
      >
        <ChevronRight size={20} />
      </button>
    </div>
  );
}