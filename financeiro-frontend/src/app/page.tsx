'use client';

import { useEffect, useState } from 'react';
import { api, Fechamento, DashboardResumo } from '@/services/api';
import { TrendingUp, TrendingDown, DollarSign, Calendar, RefreshCw, Layers } from 'lucide-react';
import { useFinanceiro } from '@/contexts/FinanceiroContext';
import { HealthCard } from '@/components/HealthCard';
import { AssistantMessage } from '@/components/AssistantMessage';

export default function DashboardPage() {
  const { lojaId, mes, ano, dataCompetenciaISO, atualizarPeriodoPorInput, periodoFormatado } = useFinanceiro();
  
  const [dados, setDados] = useState<Fechamento | null>(null);
  const [resumo, setResumo] = useState<DashboardResumo | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchDados = async () => {
    setLoading(true);
    try {
      const [fechamento, dashResumo] = await Promise.all([
        api.getFechamento(lojaId, mes, ano),
        api.getDashboardResumo(lojaId, mes, ano)
      ]);
      setDados(fechamento);
      setResumo(dashResumo);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDados();
  }, [lojaId, mes, ano]);

  const fmt = (val: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val);

  return (
    <main className="p-10 space-y-10 max-w-[1600px] mx-auto animate-enter">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Visão Geral</h1>
          <p className="text-slate-500 mt-1">Competência: <span className="capitalize font-bold text-indigo-600">{periodoFormatado}</span></p>
        </div>
        
        <div className="flex items-center gap-3 bg-white p-1.5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex items-center gap-2 px-3 py-2 bg-slate-50 rounded-lg border border-slate-100">
            <Calendar size={16} className="text-slate-500" />
            {/* 4. Input conectado ao atualizador global */}
            <input 
              type="month" 
              value={dataCompetenciaISO}
              onChange={(e) => atualizarPeriodoPorInput(e.target.value)}
              className="bg-transparent text-sm font-medium text-slate-700 outline-none cursor-pointer uppercase"
            />
          </div>
          <button 
            onClick={fetchDados}
            className="p-2.5 text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
            title="Recalcular"
          >
            <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {loading && !dados ? (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 animate-pulse">
          {[1,2,3,4].map(i => <div key={i} className="h-40 bg-slate-200 rounded-2xl"></div>)}
        </div>
      ) : dados ? (
        <>
          {/* Assistente Contextual */}
          {resumo?.mensagem_assistente && (
             <AssistantMessage message={resumo.mensagem_assistente} />
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <KpiCard title="Faturamento Bruto" value={dados.faturamento_bruto} icon={DollarSign} trend="neutral" delay="delay-0" />
            <KpiCard title="Taxas de Cartão" value={dados.total_taxas} icon={Layers} trend="down" isExpense delay="delay-100" />
            <KpiCard title="Despesas Operacionais" value={dados.total_despesas} icon={TrendingDown} trend="down" isExpense delay="delay-200" />
            <KpiCard title="Resultado Operacional" value={dados.resultado_operacional} icon={TrendingUp} trend="up" highlight delay="delay-300" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 animate-enter delay-300">

            {/* Coluna Principal: Composição */}
            <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-200/60 shadow-sm p-8 hover:shadow-md transition-shadow duration-300">
              <h3 className="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2">
                <div className="w-1 h-6 bg-indigo-500 rounded-full"></div>
                Composição do Resultado
              </h3>
              
              <div className="space-y-6">
                <ResultRow label="Faturamento Bruto" value={dados.faturamento_bruto} isBold />
                
                <div className="pl-4 border-l-2 border-slate-100 space-y-3">
                  <ResultRow label="(-) Taxas Administrativas" value={dados.total_taxas} isNegative />
                  <ResultRow label="(=) Receita Líquida" value={dados.receita_liquida} isBold />
                  <ResultRow label="(-) Despesas Operacionais" value={dados.total_despesas} isNegative />
                </div>

                <div className="pt-4 border-t border-slate-100">
                  <div className="flex justify-between items-center p-4 bg-emerald-50/50 rounded-xl border border-emerald-100/50">
                    <span className="font-bold text-emerald-900">Resultado Final</span>
                    <span className="font-mono text-2xl font-bold text-emerald-600">{fmt(dados.resultado_operacional)}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Coluna Lateral: Status + Saúde */}
            <div className="space-y-6">
              {/* Card de Saúde Financeira */}
              {resumo && (
                <HealthCard
                  status={resumo.saude_financeira}
                  percentualPago={resumo.percentual_pago}
                />
              )}

              <div className="bg-slate-900 text-slate-300 rounded-2xl p-8 shadow-lg flex flex-col justify-between relative overflow-hidden group">
                <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 rounded-full blur-3xl group-hover:bg-indigo-500/20 transition-all duration-500"></div>

                <div>
                  <h3 className="text-white font-bold text-lg mb-2">Status do Fechamento</h3>
                  <p className="text-sm text-slate-400">
                    {dados.status === 'ABERTO'
                      ? 'O fechamento atual encontra-se em aberto.'
                      : 'Este mês já foi concluído e auditado.'}
                  </p>
                </div>

                <div className="mt-8">
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`w-2.5 h-2.5 rounded-full ${dados.status === 'ABERTO' ? 'bg-yellow-400 animate-pulse' : 'bg-emerald-400'}`}></span>
                    <span className="text-xs font-bold tracking-wider uppercase text-white">{dados.status}</span>
                  </div>
                  <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                    <div
                      className={`h-full w-full rounded-full ${dados.status === 'ABERTO' ? 'bg-yellow-500' : 'bg-emerald-500'}`}
                      style={{ width: dados.status === 'ABERTO' ? '60%' : '100%' }}
                    ></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </main>
  );
}

// Subcomponentes
function KpiCard({ title, value, icon: Icon, isExpense, highlight, delay }: any) {
  const fmt = (val: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val);
  
  return (
    <div className={`
      bg-white p-6 rounded-2xl border transition-all duration-300 animate-enter ${delay}
      ${highlight 
        ? 'border-indigo-100 shadow-lg shadow-indigo-100/50 ring-1 ring-indigo-500/10' 
        : 'border-slate-200/60 shadow-sm hover:shadow-md hover:-translate-y-1'
      }
    `}>
      <div className="flex justify-between items-start mb-4">
        <div className={`p-2.5 rounded-xl ${highlight ? 'bg-indigo-100 text-indigo-600' : 'bg-slate-50 text-slate-600'}`}>
          <Icon size={20} strokeWidth={2.5} />
        </div>
        {isExpense && value > 0 && (
          <span className="text-xs font-medium text-rose-600 bg-rose-50 px-2 py-1 rounded-full">Despesa</span>
        )}
      </div>
      
      <p className="text-sm font-medium text-slate-500 mb-1">{title}</p>
      <h3 className={`text-2xl font-bold tracking-tight ${isExpense ? 'text-rose-600' : highlight ? 'text-indigo-900' : 'text-slate-900'}`}>
        {isExpense && '- '}{fmt(value)}
      </h3>
    </div>
  );
}

function ResultRow({ label, value, isNegative, isBold }: any) {
  const fmt = (val: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val);
  return (
    <div className="flex justify-between items-center group">
      <span className={`${isBold ? 'text-slate-900 font-semibold' : 'text-slate-500 group-hover:text-slate-700'} transition-colors`}>
        {label}
      </span>
      <span className={`font-mono ${isNegative ? 'text-rose-600' : 'text-slate-900'} ${isBold ? 'font-bold text-lg' : ''}`}>
        {fmt(value)}
      </span>
    </div>
  )
}