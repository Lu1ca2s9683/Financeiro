'use client';

import { useEffect, useState } from 'react';
import { api, Despesa, DespesaDetail } from '@/services/api';
import Link from 'next/link';
import { Plus, Trash2, Pencil, Search, Filter, AlertCircle, X } from 'lucide-react';
import { useFinanceiro } from '@/contexts/FinanceiroContext';
import { PeriodSelector } from '@/components/PeriodSelector';
import { DespesaForm } from '@/components/DespesaForm';

export default function DespesasPage() {
  const { lojaId, mes, ano } = useFinanceiro(); // Estado Global
  const [despesas, setDespesas] = useState<Despesa[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalMes, setTotalMes] = useState(0);

  // Estados para edição
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingDespesa, setEditingDespesa] = useState<DespesaDetail | undefined>(undefined);

  const carregar = async () => {
    setLoading(true);
    try {
      const dados = await api.getDespesas(lojaId, mes, ano);
      setDespesas(dados);
      
      const total = dados.reduce((acc, curr) => acc + Number(curr.valor_liquido), 0);
      setTotalMes(total);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const excluir = async (id: number) => {
    if (!confirm('Tem certeza que deseja excluir esta despesa?')) return;
    try {
      await api.deleteDespesa(id);
      carregar();
    } catch (error) {
      alert('Erro ao excluir');
    }
  };

  const abrirEdicao = async (id: number) => {
    try {
      const detalhes = await api.getDespesa(id);
      setEditingDespesa(detalhes);
      setIsEditModalOpen(true);
    } catch (error) {
      console.error(error);
      alert('Erro ao carregar detalhes da despesa.');
    }
  };

  const alterarStatus = async (id: number, novoStatus: string) => {
    try {
      // Feedback visual otimista poderia ser aplicado aqui, mas vamos esperar a API
      await api.updateDespesaStatus(id, novoStatus);
      carregar();
    } catch (error: any) {
      console.error(error);
      alert(error.message || 'Erro ao alterar status.');
    }
  };

  useEffect(() => {
    carregar();
  }, [lojaId, mes, ano]);

  return (
    <main className="p-8 space-y-6 animate-enter">
      
      {/* Header com Filtros e Ações */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-200 pb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Contas a Pagar</h1>
          <p className="text-slate-500 text-sm mt-1">Gestão de despesas operacionais</p>
        </div>

        <div className="flex flex-col sm:flex-row items-center gap-4 w-full md:w-auto">
          <div className="flex flex-col items-start gap-1 w-full sm:w-auto">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider pl-1">Período</span>
            <PeriodSelector />
          </div>

          <Link 
            href="/despesas/nova"
            className="w-full sm:w-auto mt-5 sm:mt-0 bg-indigo-600 text-white px-4 py-2.5 rounded-lg flex items-center justify-center gap-2 hover:bg-indigo-700 transition shadow-sm font-medium"
          >
            <Plus size={18} /> Nova Despesa
          </Link>
        </div>
      </div>

      {/* Resumo Rápido */}
      <div className="flex items-center justify-between bg-slate-50 p-4 rounded-lg border border-slate-100">
        <div className="flex items-center gap-2 text-slate-600">
          <Filter size={16} />
          <span className="text-sm font-medium">Filtrando por competência: <span className="text-indigo-600 font-bold">{mes}/{ano}</span></span>
        </div>
        <div className="text-right">
          <span className="text-xs text-slate-500 uppercase font-semibold">Total no Período</span>
          <p className="text-lg font-mono font-bold text-slate-900">
            {totalMes.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
          </p>
        </div>
      </div>

      {/* Tabela de Dados */}
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm min-h-[400px]">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-400 animate-pulse">
            <div className="w-12 h-12 bg-slate-200 rounded-full mb-4"></div>
            <p>Carregando despesas de {mes}/{ano}...</p>
          </div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase text-xs font-semibold sticky top-0">
              <tr>
                <th className="px-6 py-4">Descrição</th>
                <th className="px-6 py-4">Categoria</th>
                <th className="px-6 py-4">Competência</th>
                <th className="px-6 py-4">Valor</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {despesas.map((d) => (
                <tr key={d.id} className="hover:bg-slate-50 transition group">
                  <td className="px-6 py-4 font-medium text-slate-900">{d.descricao}</td>
                  <td className="px-6 py-4 text-slate-500">
                    <span className="bg-slate-100 px-2 py-1 rounded text-xs">{d.categoria?.nome || 'Sem Categoria'}</span>
                  </td>
                  <td className="px-6 py-4 text-slate-500 font-mono text-xs">{d.data_competencia}</td>
                  <td className="px-6 py-4 font-mono font-medium text-slate-900">
                    {Number(d.valor_liquido).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex flex-col gap-1 items-start">
                        <StatusSelector
                            currentStatus={d.status}
                            onChange={(status) => alterarStatus(d.id, status)}
                        />
                        {/* Alertas de Vencimento */}
                        {d.is_atrasado && (
                            <span className="text-[10px] font-bold text-rose-600 flex items-center gap-1 bg-rose-50 px-1.5 py-0.5 rounded border border-rose-100">
                                <AlertCircle size={10} /> VENCIDA
                            </span>
                        )}
                        {!d.is_atrasado && d.is_vencendo && d.dias_para_vencimento !== undefined && (
                             <span className="text-[10px] font-bold text-amber-600 flex items-center gap-1 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-100">
                                <AlertCircle size={10} /> VENCE EM {d.dias_para_vencimento} DIA(S)
                             </span>
                        )}
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right opacity-0 group-hover:opacity-100 transition-opacity">
                    <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => abrirEdicao(d.id)}
                          className="text-indigo-600 hover:text-indigo-800 p-2 hover:bg-indigo-50 rounded transition-colors"
                          title="Editar"
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          onClick={() => excluir(d.id)}
                          className="text-rose-500 hover:text-rose-700 p-2 hover:bg-rose-50 rounded transition-colors"
                          title="Excluir"
                        >
                          <Trash2 size={16} />
                        </button>
                    </div>
                  </td>
                </tr>
              ))}
              {despesas.length === 0 && (
                 <tr>
                   <td colSpan={6} className="px-6 py-16 text-center">
                     <div className="flex flex-col items-center justify-center text-slate-400">
                        <AlertCircle size={48} className="mb-2 text-slate-200" />
                        <p className="font-medium text-slate-500">Nenhuma despesa encontrada</p>
                        <p className="text-sm">Não há lançamentos para {mes}/{ano} nesta loja.</p>
                     </div>
                   </td>
                 </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal de Edição */}
      {isEditModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div className="bg-white rounded-xl shadow-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto animate-in zoom-in-95 duration-200">
                <div className="flex justify-between items-center p-6 border-b border-slate-100 sticky top-0 bg-white z-10">
                    <h2 className="text-xl font-bold text-slate-900">Editar Despesa</h2>
                    <button
                        onClick={() => setIsEditModalOpen(false)}
                        className="text-slate-400 hover:text-slate-600 hover:bg-slate-100 p-2 rounded-full transition"
                    >
                        <X size={20} />
                    </button>
                </div>
                <div className="p-6">
                    <DespesaForm
                        initialData={editingDespesa}
                        onSuccess={() => {
                            setIsEditModalOpen(false);
                            carregar();
                        }}
                        onCancel={() => setIsEditModalOpen(false)}
                    />
                </div>
            </div>
        </div>
      )}

    </main>
  );
}

function StatusSelector({ currentStatus, onChange }: { currentStatus: string, onChange: (s: string) => void }) {
  const styles: any = {
    'PREVISTO': 'bg-blue-50 text-blue-700 border-blue-100 hover:bg-blue-100',
    'PAGO': 'bg-emerald-50 text-emerald-700 border-emerald-100 hover:bg-emerald-100',
    'ATRASADO': 'bg-rose-50 text-rose-700 border-rose-100 hover:bg-rose-100',
    'CANCELADO': 'bg-slate-100 text-slate-500 border-slate-200 hover:bg-slate-200',
  };
  
  const currentStyle = styles[currentStatus] || styles['PREVISTO'];

  return (
    <div className="relative inline-block">
        <select
            value={currentStatus}
            onChange={(e) => onChange(e.target.value)}
            className={`
                appearance-none cursor-pointer
                px-3 py-1 pr-6 rounded-full text-xs font-bold border
                outline-none focus:ring-2 focus:ring-offset-1 focus:ring-indigo-500
                transition-colors
                ${currentStyle}
            `}
        >
            <option value="PREVISTO">PREVISTO</option>
            <option value="PAGO">PAGO</option>
            <option value="ATRASADO">ATRASADO</option>
            <option value="CANCELADO">CANCELADO</option>
        </select>
        {/* Ícone de seta personalizado para indicar dropdown */}
        <div className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none opacity-50">
            <svg width="10" height="6" viewBox="0 0 10 6" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
                <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
        </div>
    </div>
  );
}
