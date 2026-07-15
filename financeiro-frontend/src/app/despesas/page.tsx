'use client';

import { useEffect, useState } from 'react';
import { api, Despesa, DespesaDetail } from '@/services/api';
import Link from 'next/link';
import { Plus, Trash2, Pencil, Search, Filter, AlertCircle, X } from 'lucide-react';

import { useDateFilter } from '@/contexts/DateFilterContext';
import { useAuth } from '@/contexts/AuthContext';
import { PeriodSelector } from '@/components/PeriodSelector';
import { DespesaForm } from '@/components/DespesaForm';

export default function DespesasPage() {

  const { activeLoja, canEdit } = useAuth();
  const { mes, ano, setMes, setAno } = useDateFilter();
  const [despesas, setDespesas] = useState<Despesa[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [splits, setSplits] = useState<any[]>([]);
  const [totalMes, setTotalMes] = useState(0);

  // Estados para edição
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingDespesa, setEditingDespesa] = useState<DespesaDetail | undefined>(undefined);


  const toggleExpand = async (id: number) => {
      if (expandedId === id) {
          setExpandedId(null);
          setSplits([]);
      } else {
          setExpandedId(id);
          try {
              const details = await api.getDespesa(id);
              setSplits(details.splits || []);
          } catch (e) {
              console.error(e);
          }
      }
  };

  const carregar = async () => {
    setLoading(true);
    try {
      const dados = await api.getDespesas(activeLoja?.id || 0, mes, ano);
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


  useEffect(() => {
    carregar();
  }, [activeLoja?.id || 0, mes, ano]);

  return (
    <main className="p-8 space-y-6 animate-enter">
      
      {/* Header com Filtros e Ações */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-200 pb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Contas a Pagar</h1>
          <p className="text-slate-500 text-sm mt-1">Gestão de despesas operacionais</p>
        </div>


        <div className="flex flex-col md:flex-row items-center gap-4 w-full md:w-auto">
          <div className="flex flex-col items-start gap-1 w-full md:w-auto">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider pl-1">Período</span>
            <PeriodSelector />
          </div>

          {canEdit && (
            <>
              <input
                 type="file"
                 id="import-extrato"
                 className="hidden"
                 accept=".ofx,.ofc"
                 onChange={async (e) => {
                     const file = e.target.files?.[0];
                     if (file) {
                        try {
                            const formData = new FormData();
                            formData.append('file', file);

                            const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
                            const lojaId = typeof window !== 'undefined' ? localStorage.getItem('active_loja_id') || '1' : '1';

                            const res = await fetch(`http://localhost:8000/api/financeiro/extrato/importar/${lojaId}`, {
                                method: 'POST',
                                headers: {
                                    'Authorization': `Bearer ${token}`
                                },
                                body: formData
                            });

                            if (res.ok) {
                                alert('Extrato importado com sucesso!');
                                window.location.reload();
                            } else {
                                const errorData = await res.json();
                                alert('Erro ao importar extrato: ' + (errorData.detail || 'Erro desconhecido'));
                            }
                        } catch (error) {
                            console.error('Erro na importação:', error);
                            alert('Erro de conexão ao tentar importar extrato.');
                        }
                     }
                 }}
              />
              <label
                  htmlFor="import-extrato"
                  className="w-full sm:w-auto bg-white text-slate-700 border border-slate-300 px-4 py-2.5 rounded-lg flex items-center justify-center gap-2 hover:bg-slate-50 transition shadow-sm font-medium cursor-pointer"
              >
                  <Plus size={18} /> Importar Extrato
              </label>

              <Link
                  href={`/despesas/nova?mes=${mes}&ano=${ano}`}
                  className="w-full sm:w-auto bg-indigo-600 text-white px-4 py-2.5 rounded-lg flex items-center justify-center gap-2 hover:bg-indigo-700 transition shadow-sm font-medium"
              >
                  <Plus size={18} /> Nova Despesa
              </Link>
            </>
          )}
        </div>

      </div>

    </main>
  );
}


