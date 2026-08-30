/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars, react-hooks/exhaustive-deps, react-hooks/set-state-in-effect, @typescript-eslint/no-require-imports */
'use client';

import { useEffect, useState } from 'react';
import {
  api,
  Categoria,
  ContaBancaria,
  Despesa,
  DespesaDetail,
  ExtratoItem,
  VendedorAtivo,
} from '@/services/api';
import Link from 'next/link';
import { Plus, Trash2, Pencil, Search, Filter, AlertCircle, X } from 'lucide-react';

import { useDateFilter } from '@/contexts/DateFilterContext';
import { useAuth } from '@/contexts/AuthContext';
import { PeriodSelector } from '@/components/PeriodSelector';
import { DespesaForm } from '@/components/DespesaForm';
import { centsToDecimalString, formatCents, parseMoneyToCents } from '@/utils/money';

interface RateioImportado {
  descricao: string;
  valor: string;
  categoria_id: string;
  vendedor_id_externo: string;
}

interface DespesaImportada extends Omit<ExtratoItem, 'categoria_sugerida_id'> {
  _tempId: number;
  expanded: boolean;
  categoria_sugerida_id?: number | string | null;
  vendedor_id_externo: string;
  rateios: RateioImportado[];
}

export default function DespesasPage() {

  const { activeLoja, canEdit } = useAuth();
  const { mes, ano, setMes, setAno } = useDateFilter();
  const [despesas, setDespesas] = useState<Despesa[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [splits, setSplits] = useState<any[]>([]);
  const [totalMes, setTotalMes] = useState(0);
  
  // Estado para extrato importado pendente de categorização
  const [importedDespesas, setImportedDespesas] = useState<DespesaImportada[]>([]);
  const [categoriasPendentes, setCategoriasPendentes] = useState<Categoria[]>([]);
  const [contasBancarias, setContasBancarias] = useState<ContaBancaria[]>([]);
  const [contaOrigemId, setContaOrigemId] = useState('');
  const [vendedores, setVendedores] = useState<VendedorAtivo[]>([]);

  useEffect(() => {
      api.getCategorias().then(setCategoriasPendentes).catch(console.error);
  }, []);

  useEffect(() => {
      if (!activeLoja?.id) {
          setContasBancarias([]);
          setVendedores([]);
          setContaOrigemId('');
          return;
      }
      api.getContasBancarias()
          .then(contas => setContasBancarias(contas.filter(conta => conta.ativo)))
          .catch(console.error);
      api.getVendedoresAtivos(activeLoja.id).then(setVendedores).catch(console.error);
      setContaOrigemId('');
      setImportedDespesas([]);
  }, [activeLoja?.id]);

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
      
      // Correção TypeScript: 'curr: any' ignora a verificação estrita para esta operação matemática
      const total = dados.reduce((acc, curr: any) => acc + Number(curr.valor_liquido || curr.valor), 0);
      setTotalMes(total);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  // Função Auxiliar para cruzar o ID da categoria com o Nome Real
  const getCategoriaNome = (d: any) => {
    if (d.categoria_nome) return d.categoria_nome;
    if (d.categoria && typeof d.categoria === 'object' && d.categoria.nome) return d.categoria.nome;
    
    const catId = d.categoria_id || (typeof d.categoria !== 'object' ? d.categoria : null);
    if (catId) {
        const found = categoriasPendentes.find(c => String(c.id) === String(catId));
        if (found) return found.nome;
    }
    return 'Sem Categoria';
  };

  const salvarImportada = async (index: number) => {
      const item = importedDespesas[index];
      if (item.ja_importada) return;
      if (!contaOrigemId) {
          alert('Selecione a conta bancária do extrato.');
          return;
      }
      if (!item.categoria_sugerida_id) {
          alert('Por favor, selecione uma categoria para a despesa.');
          return;
      }
      try {
          const valorCentavos = parseMoneyToCents(item.valor);
          const rateiosCentavos = item.rateios.map(rateio => parseMoneyToCents(rateio.valor));
          if (valorCentavos === null || valorCentavos <= 0) {
              throw new Error('Valor importado inválido.');
          }
          if (item.rateios.length > 0 && (
              rateiosCentavos.some(valor => valor === null || valor <= 0)
              || rateiosCentavos.reduce<number>((total, valor) => total + (valor ?? 0), 0) !== valorCentavos
          )) {
              throw new Error('O rateio deve consumir exatamente o valor da despesa.');
          }
          const payload = {
              descricao: item.descricao_original,
              valor: centsToDecimalString(valorCentavos),
              categoria_id: Number(item.categoria_sugerida_id),
              loja_id: activeLoja?.id || Number(localStorage.getItem('active_loja_id')) || 1,
              data_competencia: item.data_transacao,
              data_transacao: item.data_transacao,
              conta_origem_id: Number(contaOrigemId),
              origem_lancamento: 'OFX',
              ofx_fitid: item.fitid || null,
              ofx_fingerprint: item.fingerprint,
              descricao_original_extrato: item.descricao_original,
              ofx_import_token: item.ofx_import_token,
              vendedor_id_externo: item.rateios.length === 0 && item.vendedor_id_externo
                  ? Number(item.vendedor_id_externo)
                  : null,
              rateios: item.rateios.map((r, rateioIndex) => ({
                  descricao: r.descricao,
                  valor: centsToDecimalString(rateiosCentavos[rateioIndex] as number),
                  categoria_id: r.categoria_id ? Number(r.categoria_id) : undefined,
                  vendedor_id_externo: r.vendedor_id_externo
                      ? Number(r.vendedor_id_externo)
                      : null,
              }))
          };
          await api.createDespesa(payload);
          const newImported = [...importedDespesas];
          newImported.splice(index, 1);
          setImportedDespesas(newImported);
          carregar(); // Recarrega a tabela principal
      } catch (error) {
          console.error(error);
          alert(error instanceof Error ? error.message : 'Erro ao salvar despesa importada.');
      }
  };

  const toggleImportedExpanded = (index: number) => {
      const newImported = [...importedDespesas];
      newImported[index].expanded = !newImported[index].expanded;
      setImportedDespesas(newImported);
  };

  const updateImportedRateio = (
      index: number,
      rateioIndex: number,
      field: keyof RateioImportado,
      value: string
  ) => {
      const newImported = [...importedDespesas];
      newImported[index].rateios[rateioIndex][field] = value;
      setImportedDespesas(newImported);
  };

  const addImportedRateio = (index: number) => {
      const newImported = [...importedDespesas];
      newImported[index].vendedor_id_externo = '';
      newImported[index].rateios.push({
          descricao: '',
          valor: '',
          categoria_id: '',
          vendedor_id_externo: '',
      });
      newImported[index].expanded = true;
      setImportedDespesas(newImported);
  };

  const categoriaPorId = (id: number | string | null | undefined) =>
      categoriasPendentes.find(categoria => String(categoria.id) === String(id));

  const categoriaEfetivaRateio = (item: DespesaImportada, rateio: RateioImportado) =>
      categoriaPorId(rateio.categoria_id || item.categoria_sugerida_id);

  const rateioImportadoEmCentavos = (item: DespesaImportada) => {
      const valorTotal = parseMoneyToCents(item.valor) ?? 0;
      const valores = item.rateios.map(rateio => parseMoneyToCents(rateio.valor));
      const totalRateado = valores.reduce<number>((total, valor) => total + (valor ?? 0), 0);
      return {
          valorTotal,
          totalRateado,
          saldo: valorTotal - totalRateado,
          valido: item.rateios.length === 0
              || (valores.every(valor => valor !== null && valor > 0) && valorTotal === totalRateado),
      };
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
              <select
                  aria-label="Conta bancária do extrato"
                  className="w-full sm:w-64 bg-white text-slate-700 border border-slate-300 px-3 py-2.5 rounded-lg shadow-sm"
                  value={contaOrigemId}
                  onChange={event => {
                      setContaOrigemId(event.target.value);
                      setImportedDespesas([]);
                  }}
              >
                  <option value="">Conta bancária do extrato...</option>
                  {contasBancarias.map(conta => (
                      <option key={conta.id} value={conta.id}>{conta.nome}</option>
                  ))}
              </select>
              <input
                 type="file"
                 id="import-extrato"
                 className="hidden"
                 accept=".ofx,.ofc"
                 onChange={async (e) => {
                     const file = e.target.files?.[0];
                     if (file) {
                        try {
                            if (!activeLoja?.id) {
                                alert("Erro: Selecione uma loja antes de importar o extrato.");
                                return;
                            }
                            if (!contaOrigemId) {
                                alert("Selecione a conta bancária que gerou o extrato.");
                                e.target.value = '';
                                return;
                            }

                            const extratoTransacoes = await api.importarExtratoDespesas(
                                activeLoja.id,
                                Number(contaOrigemId),
                                file
                            );
                            const saidas = extratoTransacoes.filter((t) => t.tipo === 'SAIDA');
                            setImportedDespesas(saidas.map((t, idx) => ({
                                ...t,
                                _tempId: idx,
                                expanded: false,
                                vendedor_id_externo: '',
                                rateios: [],
                            })));

                            const jaImportadas = saidas.filter(item => item.ja_importada).length;
                            alert(
                                `Extrato lido com sucesso! ${saidas.length - jaImportadas} saídas aguardam categorização.`
                                + (jaImportadas > 0
                                    ? `\n\n${jaImportadas} transações já existem e estão identificadas na lista.`
                                    : '')
                            );
                        } catch (error) {
                            console.error('Erro na importação:', error);
                            alert('Erro de conexão ao tentar importar extrato.');
                        }
                     }
                 }}
              />
              <label
                  htmlFor="import-extrato"
                  aria-disabled={!contaOrigemId}
                  className={`w-full sm:w-auto bg-white text-slate-700 border border-slate-300 px-4 py-2.5 rounded-lg flex items-center justify-center gap-2 transition shadow-sm font-medium ${contaOrigemId ? 'hover:bg-slate-50 cursor-pointer' : 'opacity-50 cursor-not-allowed'}`}
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
                  {importedDespesas.map((item, index) => {
                      const rateioInfo = rateioImportadoEmCentavos(item);
                      const categoriaPrincipalImportada = categoriaPorId(item.categoria_sugerida_id);
                      return (
                      <div key={item._tempId} className={`bg-white border rounded-lg p-4 shadow-sm flex flex-col gap-4 ${item.ja_importada ? 'border-slate-200 opacity-70' : 'border-amber-100'}`}>
                          {item.ja_importada && (
                              <div className="rounded-md bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-700">
                                  Esta transação já existe no Financeiro
                                  {item.duplicate_reason ? ` (${item.duplicate_reason})` : ''}.
                              </div>
                          )}
                          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                              <div className="flex-1">
                                  <div className="text-xs text-slate-500 font-mono mb-1">{item.data_transacao}</div>
                                  <div className="font-semibold text-slate-900">{item.descricao_original}</div>
                              </div>
                              <div className="font-mono font-bold text-rose-600 text-lg">
                                  - {formatCents(rateioInfo.valorTotal)}
                              </div>
                              <div className="w-full md:w-64">
                                  <select
                                      disabled={item.ja_importada}
                                      className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm"
                                      value={item.categoria_sugerida_id || ''}
                                      onChange={(e) => {
                                          const newImported = [...importedDespesas];
                                          newImported[index].categoria_sugerida_id = e.target.value;
                                          if (categoriaPorId(e.target.value)?.grupo_contabil !== 'PESSOAL') {
                                              newImported[index].vendedor_id_externo = '';
                                              newImported[index].rateios = newImported[index].rateios.map(rateio => (
                                                  rateio.categoria_id
                                                      ? rateio
                                                      : {...rateio, vendedor_id_externo: ''}
                                              ));
                                          }
                                          setImportedDespesas(newImported);
                                      }}
                                  >
                                      <option value="">Selecione a categoria...</option>
                                      {categoriasPendentes.map(c => (
                                          <option key={c.id} value={c.id}>{c.nome}</option>
                                      ))}
                                  </select>
                                  {categoriaPrincipalImportada?.grupo_contabil === 'PESSOAL' && item.rateios.length === 0 && (
                                      <select
                                          disabled={item.ja_importada}
                                          aria-label={`Vendedor da transação ${index + 1}`}
                                          className="mt-2 w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm"
                                          value={item.vendedor_id_externo}
                                          onChange={event => {
                                              const newImported = [...importedDespesas];
                                              newImported[index].vendedor_id_externo = event.target.value;
                                              setImportedDespesas(newImported);
                                          }}
                                      >
                                          <option value="">Sem vendedor</option>
                                          {vendedores.map(vendedor => (
                                              <option key={vendedor.id} value={vendedor.id}>{vendedor.nome}</option>
                                          ))}
                                      </select>
                                  )}
                              </div>
                              <div className="flex gap-2 w-full md:w-auto">
                                  <button disabled={item.ja_importada} onClick={() => toggleImportedExpanded(index)} className="px-3 py-2 text-sm font-medium border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition disabled:cursor-not-allowed">
                                      Rateio ({item.rateios.length})
                                  </button>
                                  <button
                                      disabled={item.ja_importada || !rateioInfo.valido}
                                      onClick={() => salvarImportada(index)}
                                      className="px-4 py-2 text-sm font-medium bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                                  >
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
                                          {item.rateios.map((r, rIdx) => (
                                              <div key={rIdx} className="grid grid-cols-1 md:grid-cols-5 gap-3">
                                                  <input
                                                      type="text"
                                                      placeholder="Descrição específica"
                                                      className="md:col-span-2 text-sm border border-slate-300 rounded px-3 py-2"
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
                                                  <select
                                                      className="w-full text-sm border border-slate-300 rounded px-3 py-2"
                                                      value={r.categoria_id}
                                                      onChange={(e) => {
                                                          const newImported = [...importedDespesas];
                                                          newImported[index].rateios[rIdx].categoria_id = e.target.value;
                                                          if (categoriaPorId(e.target.value || item.categoria_sugerida_id)?.grupo_contabil !== 'PESSOAL') {
                                                              newImported[index].rateios[rIdx].vendedor_id_externo = '';
                                                          }
                                                          setImportedDespesas(newImported);
                                                      }}
                                                  >
                                                      <option value="">(Usar principal)</option>
                                                      {categoriasPendentes.map(c => (
                                                          <option key={c.id} value={c.id}>{c.nome}</option>
                                                      ))}
                                                  </select>
                                                  <div className="flex gap-2">
                                                      {categoriaEfetivaRateio(item, r)?.grupo_contabil === 'PESSOAL' ? (
                                                          <select
                                                              aria-label={`Vendedor do rateio importado ${rIdx + 1}`}
                                                              className="w-full text-sm border border-slate-300 rounded px-3 py-2"
                                                              value={r.vendedor_id_externo}
                                                              onChange={event => updateImportedRateio(index, rIdx, 'vendedor_id_externo', event.target.value)}
                                                          >
                                                              <option value="">Sem vendedor</option>
                                                              {vendedores.map(vendedor => (
                                                                  <option key={vendedor.id} value={vendedor.id}>{vendedor.nome}</option>
                                                              ))}
                                                          </select>
                                                      ) : <span className="w-full px-2 py-2 text-xs text-slate-400">Sem vendedor</span>}
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
                                          <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm space-y-2">
                                              <div className="flex justify-between"><span>Valor da despesa</span><strong>{formatCents(rateioInfo.valorTotal)}</strong></div>
                                              <div className="flex justify-between"><span>Total rateado</span><strong>{formatCents(rateioInfo.totalRateado)}</strong></div>
                                              <div className={`flex justify-between border-t border-slate-200 pt-2 ${rateioInfo.saldo === 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
                                                  <span>Saldo a ratear</span><strong>{formatCents(rateioInfo.saldo)}</strong>
                                              </div>
                                          </div>
                                      </div>
                                  )}
                              </div>
                          )}
                      </div>
                      );
                  })}
              </div>
          </div>
      )}

      {/* Tabela Principal de Despesas Salvas */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="p-4 border-b border-slate-200 bg-slate-50 flex justify-between items-center">
          <h2 className="text-lg font-bold text-slate-800">Despesas Registradas</h2>
          <div className="text-sm font-semibold text-slate-600">
            Total: {totalMes.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-white border-b border-slate-200 text-slate-500 text-xs uppercase tracking-wider">
                <th className="p-4 font-semibold">Data</th>
                <th className="p-4 font-semibold">Descrição</th>
                <th className="p-4 font-semibold">Categoria</th>
                <th className="p-4 font-semibold text-right">Valor</th>
                <th className="p-4 font-semibold text-center">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-slate-500 animate-pulse">
                    Carregando despesas...
                  </td>
                </tr>
              ) : despesas.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-slate-500">
                    Nenhuma despesa encontrada para este período.
                  </td>
                </tr>
              ) : (
                despesas.map(d => (
                  <tr key={d.id} className="hover:bg-slate-50 transition-colors">
                    <td className="p-4 text-sm text-slate-600">{d.data_transacao}</td>
                    <td className="p-4 text-sm font-medium text-slate-900">{d.descricao}</td>
                    <td className="p-4 text-sm text-slate-600">
                        <span className="bg-slate-100 px-2 py-1 rounded-md border border-slate-200">
                            {getCategoriaNome(d)}
                        </span>
                    </td>
                    <td className="p-4 text-sm font-bold text-rose-600 text-right">
                      - {Number((d as any).valor_liquido || (d as any).valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                    </td>
                    <td className="p-4 text-center">
                      <button 
                        onClick={() => excluir(d.id)} 
                        className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors" 
                        title="Excluir"
                      >
                        <Trash2 size={18} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

    </main>
  );
}
