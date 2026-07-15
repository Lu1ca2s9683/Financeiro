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
  
  // Estado para extrato importado pendente de categorização
  const [importedDespesas, setImportedDespesas] = useState<any[]>([]);
  const [categoriasPendentes, setCategoriasPendentes] = useState<any[]>([]);

  useEffect(() => {
      api.getCategorias().then(setCategoriasPendentes).catch(console.error);
  }, []);

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


  const salvarImportada = async (index: number) => {
      const item = importedDespesas[index];
      if (!item.categoria_sugerida_id) {
          alert('Por favor, selecione uma categoria para a despesa.');
          return;
      }
      try {
          const payload = {
              descricao: item.descricao_original,
              valor: item.valor,
              categoria_id: item.categoria_sugerida_id,
              data_competencia: item.data_transacao,
              data_transacao: item.data_transacao,
              rateios: item.rateios.map((r: any) => ({
                  descricao: r.descricao,
                  valor: parseFloat(r.valor.replace(',', '.')),
                  categoria_id: r.categoria_id ? Number(r.categoria_id) : undefined
              }))
          };
          await api.createDespesa(payload);
          const newImported = [...importedDespesas];
          newImported.splice(index, 1);
          setImportedDespesas(newImported);
          carregar(); // Recarrega a tabela principal
      } catch (error) {
          console.error(error);
          alert('Erro ao salvar despesa importada.');
      }
  };

  const toggleImportedExpanded = (index: number) => {
      const newImported = [...importedDespesas];
      newImported[index].expanded = !newImported[index].expanded;
      setImportedDespesas(newImported);
  };

  const updateImportedRateio = (index: number, rateioIndex: number, field: string, value: string) => {
      const newImported = [...importedDespesas];
      newImported[index].rateios[rateioIndex][field] = value;
      setImportedDespesas(newImported);
  };

  const addImportedRateio = (index: number) => {
      const newImported = [...importedDespesas];
      newImported[index].rateios.push({ descricao: '', valor: '', categoria_id: '' });
      newImported[index].expanded = true;
      setImportedDespesas(newImported);
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

  // CORREÇÃO: Faltava o "return (" aqui!
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

                            const res = await fetch(`http://localhost:8000/api/financeiro/extrato/importar-despesas/${lojaId}`, {
                                method: 'POST',
                                headers: {
                                    'Authorization': `Bearer ${token}`
                                },
                                body: formData
                            });

                            if (res.ok) {
                                const extratoTransacoes = await res.json();
                                setImportedDespesas(extratoTransacoes.map((t: any, idx: number) => ({ ...t, _tempId: idx, expanded: false, rateios: [] })));
                                alert(`Extrato lido com sucesso! ${extratoTransacoes.length} saídas aguardam categorização.`);
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

      {/* Seção de Importações Pendentes */}
      {importedDespesas.length > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-xl shadow-sm p-6 mb-6">
              <h2 className="text-lg font-bold text-amber-900 mb-4 flex items-center gap-2">
                  <AlertCircle size={20} />
                  Despesas Importadas Pendentes de Categorização ({importedDespesas.length})
              </h2>
              <div className="space-y-4">
                  {importedDespesas.map((item, index) => (
                      <div key={item._tempId} className="bg-white border border-amber-100 rounded-lg p-4 shadow-sm flex flex-col gap-4">
                          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                              <div className="flex-1">
                                  <div className="text-xs text-slate-500 font-mono mb-1">{item.data_transacao}</div>
                                  <div className="font-semibold text-slate-900">{item.descricao_original}</div>
                              </div>
                              <div className="font-mono font-bold text-rose-600 text-lg">
                                  - {Number(item.valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                              </div>
                              <div className="w-full md:w-64">
                                  <select
                                      className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm"
                                      value={item.categoria_sugerida_id || ''}
                                      onChange={(e) => {
                                          const newImported = [...importedDespesas];
                                          newImported[index].categoria_sugerida_id = e.target.value;
                                          setImportedDespesas(newImported);
                                      }}
                                  >
                                      <option value="">Selecione a categoria...</option>
                                      {categoriasPendentes.map(c => (
                                          <option key={c.id} value={c.id}>{c.nome}</option>
                                      ))}
                                  </select>
                              </div>
                              <div className="flex gap-2 w-full md:w-auto">
                                  <button onClick={() => toggleImportedExpanded(index)} className="px-3 py-2 text-sm font-medium border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition">
                                      Rateio ({item.rateios.length})
                                  </button>
                                  <button onClick={() => salvarImportada(index)} className="px-4 py-2 text-sm font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition">
                                      Salvar
                                  </button>
                              </div>
                          </div>

                          {/* Sanfona de Rateio */}
                          {item.expanded && (
                              <div className="pt-4 border-t border-slate-100 bg-slate-50/50 p-4 rounded-lg mt-2">
                                  <div className="flex justify-between items-center mb-4">
                                      <h3 className="text-sm font-semibold text-slate-700">Divisão da Despesa (Rateio)</h3>
                                      <button onClick={() => addImportedRateio(index)} className="text-xs text-indigo-600 font-medium hover:underline">+ Adicionar Linha</button>
                                  </div>

                                  {item.rateios.length === 0 ? (
                                      <p className="text-xs text-slate-500">Nenhum rateio configurado. O valor total irá para a categoria principal.</p>
                                  ) : (
                                      <div className="space-y-3">
                                          {item.rateios.map((r: any, rIdx: number) => (
                                              <div key={rIdx} className="grid grid-cols-1 md:grid-cols-4 gap-3">
                                                  <input
                                                      type="text"
                                                      placeholder="Descrição específica"
                                                      className="col-span-2 text-sm border border-slate-300 rounded px-3 py-2"
                                                      value={r.descricao}
                                                      onChange={(e) => updateImportedRateio(index, rIdx, 'descricao', e.target.value)}
                                                  />
                                                  <input
                                                      type="number"
                                                      step="0.01"
                                                      placeholder="Valor R$"
                                                      className="text-sm border border-slate-300 rounded px-3 py-2"
                                                      value={r.valor}
                                                      onChange={(e) => updateImportedRateio(index, rIdx, 'valor', e.target.value)}
                                                  />
                                                  <div className="flex gap-2">
                                                      <select
                                                          className="w-full text-sm border border-slate-300 rounded px-3 py-2"
                                                          value={r.categoria_id}
                                                          onChange={(e) => updateImportedRateio(index, rIdx, 'categoria_id', e.target.value)}
                                                      >
                                                          <option value="">(Usar principal)</option>
                                                          {categoriasPendentes.map(c => (
                                                              <option key={c.id} value={c.id}>{c.nome}</option>
                                                          ))}
                                                      </select>
                                                      <button
                                                          onClick={() => {
                                                              const newImported = [...importedDespesas];
                                                              newImported[index].rateios.splice(rIdx, 1);
                                                              setImportedDespesas(newImported);
                                                          }}
                                                          className="text-rose-500 hover:bg-rose-50 px-2 rounded"
                                                      >
                                                          <X size={16} />
                                                      </button>
                                                  </div>
                                              </div>
                                          ))}
                                      </div>
                                  )}
                              </div>
                          )}
                      </div>
                  ))}
              </div>
          </div>
      )}

      {/* ALERTA: A TABELA DE DESPESAS FOI REMOVIDA AQUI PELO JULES */}
      {/* Será necessário pedir-lhe para a reinserir depois que a build funcionar */}

    </main>
  );
}
