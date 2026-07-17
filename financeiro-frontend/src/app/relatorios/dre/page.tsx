/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars, react-hooks/exhaustive-deps, react-hooks/set-state-in-effect, @typescript-eslint/no-require-imports */
'use client';
import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/services/api';
import { useDateFilter } from '@/contexts/DateFilterContext';
import { Download, FileCode, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react';
import { PeriodSelector } from '@/components/PeriodSelector';

export default function DreGerencialPage() {
    const { activeLoja } = useAuth();
    const { mes, ano } = useDateFilter();
    const [dre, setDre] = useState<import('@/services/api').DREData | null>(null);
    const [loading, setLoading] = useState(true);
    const [downloadingPdf, setDownloadingPdf] = useState(false);
    const [downloadingXml, setDownloadingXml] = useState(false);
    const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
    const [expandedCats, setExpandedCats] = useState<Record<string, boolean>>({});

    useEffect(() => {
        if (!activeLoja) return;
        setLoading(true);
        api.getDre(activeLoja.id, mes, ano)
           .then(setDre)
           .catch(console.error)
           .finally(() => setLoading(false));
    }, [activeLoja, mes, ano]);

    if (!activeLoja) return null;

    const formatCurrency = (val: number | string) => {
        return Number(val || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    };

    const handlePdf = async () => {
        setDownloadingPdf(true);
        try {
            await api.downloadDrePdf(activeLoja.id, mes, ano);
        } catch(e) {
            alert("Erro ao gerar PDF");
        }
        setDownloadingPdf(false);
    };

    const handleXml = async () => {
        setDownloadingXml(true);
        try {
            await api.downloadDreXml(activeLoja.id, mes, ano);
        } catch(e) {
            alert("Erro ao gerar XML");
        }
        setDownloadingXml(false);
    };

    const toggleGroup = (codigo: string) => {
        setExpandedGroups(prev => ({ ...prev, [codigo]: !prev[codigo] }));
    };

    const toggleCat = (id: string) => {
        setExpandedCats(prev => ({ ...prev, [id]: !prev[id] }));
    };

    return (
        <main className="p-4 sm:p-8 space-y-8 animate-enter max-w-5xl mx-auto font-sans">
            {/* A. Cabeçalho */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-end border-b-2 border-slate-900 pb-4 gap-4">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight uppercase">Demonstrativo do Resultado do Exercício</h1>
                    <p className="text-slate-500 mt-1 font-medium">{activeLoja?.nome || "Loja"} | DRE Gerencial Consolidado (Regime de Caixa)</p>
                </div>
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                    <PeriodSelector />
                    <div className="flex gap-2">
                        <button onClick={handlePdf} disabled={downloadingPdf} className="flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors border border-slate-300 px-4 py-2 rounded-md shadow-sm h-[40px] disabled:opacity-50">
                            <Download size={16} /> {downloadingPdf ? 'Gerando...' : 'PDF'}
                        </button>
                        <button onClick={handleXml} disabled={downloadingXml} className="flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors border border-slate-300 px-4 py-2 rounded-md shadow-sm h-[40px] disabled:opacity-50">
                            <FileCode size={16} /> {downloadingXml ? 'Gerando...' : 'XML'}
                        </button>
                    </div>
                </div>
            </div>

            {loading ? (
                <div className="flex justify-center p-20 text-slate-400">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900"></div>
                </div>
            ) : dre ? (
                <div className="space-y-8">
                    {/* E. Qualidade de Dados (Alertas) */}
                    {dre.qualidade_dados?.possui_rateios_invalidos && (
                        <div className="bg-rose-50 border border-rose-200 text-rose-700 p-4 rounded-lg flex items-start gap-3">
                            <AlertCircle className="shrink-0 mt-0.5" size={20} />
                            <div>
                                <p className="font-semibold text-sm">Aviso de Qualidade de Dados</p>
                                <p className="text-sm">Existem despesas cujo total rateado não corresponde ao valor da despesa. Esses registros foram considerados pela categoria principal e necessitam de revisão.</p>
                            </div>
                        </div>
                    )}

                    {/* B. Resumo Executivo */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-center">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Receita Bruta</span>
                            <span className="text-lg font-bold text-slate-900">{formatCurrency(dre.resumo.receita_bruta)}</span>
                        </div>
                        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-center">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Receita Líquida</span>
                            <span className="text-lg font-bold text-indigo-600">{formatCurrency(dre.resumo.receita_liquida)}</span>
                        </div>
                        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-center">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Lucro Bruto</span>
                            <span className="text-lg font-bold text-emerald-600">{formatCurrency(dre.resumo.lucro_bruto)} <span className="text-xs text-emerald-600/70">({dre.resumo.margem_bruta_percentual}%)</span></span>
                        </div>
                        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-center">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Resultado Oper.</span>
                            <span className="text-lg font-bold text-slate-900">{formatCurrency(dre.resumo.resultado_operacional)} <span className="text-xs text-slate-500">({dre.resumo.margem_operacional_percentual}%)</span></span>
                        </div>
                        <div className="bg-slate-900 p-4 rounded-xl shadow-sm flex flex-col justify-center col-span-2 sm:col-span-1 md:col-span-4 lg:col-span-1">
                            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-1">Resultado Líquido</span>
                            <span className="text-xl font-bold text-white">{formatCurrency(dre.resumo.lucro_liquido)} <span className="text-xs text-slate-400">({dre.resumo.margem_liquida_percentual}%)</span></span>
                        </div>
                    </div>

                    {/* C. DRE em cascata */}
                    <div className="bg-white border border-slate-200 shadow-sm p-4 sm:p-8 overflow-x-auto">
                        <table className="w-full text-left text-sm table-auto border-collapse min-w-[600px]">
                            <colgroup>
                                <col className="w-[10%]" />
                                <col className="w-[60%]" />
                                <col className="w-[20%]" />
                                <col className="w-[10%]" />
                            </colgroup>
                            <tbody className="divide-y divide-slate-100">
                                <tr className="border-b-2 border-slate-200">
                                    <td className="py-3 font-bold text-slate-900 uppercase text-xs tracking-wider">Cód</td>
                                    <td className="py-3 font-bold text-slate-900 uppercase text-xs tracking-wider">Descrição</td>
                                    <td className="py-3 font-bold text-right text-slate-900 uppercase text-xs tracking-wider">Valor (R$)</td>
                                    <td className="py-3 font-bold text-right text-slate-900 uppercase text-xs tracking-wider">% Rec</td>
                                </tr>

                                {dre.linhas.map((linha: import('@/services/api').DRELinha) => (
                                    <tr key={linha.codigo} className={`${linha.tipo === 'TOTAL' ? 'bg-slate-50 border-t border-slate-200' : ''} ${linha.codigo === "14" ? 'border-t-4 border-slate-900 bg-slate-100' : ''}`}>
                                        <td className={`py-3 text-slate-500 font-mono ${linha.tipo === 'TOTAL' ? 'font-bold text-slate-900' : ''} ${linha.codigo === "14" ? 'font-black text-slate-900 text-lg' : ''}`}>{linha.codigo}</td>
                                        <td className={`py-3 ${linha.tipo === 'TOTAL' ? 'font-bold text-slate-900' : 'text-slate-600'} ${linha.nivel === 1 ? 'pl-6 border-l-2 border-slate-100' : ''} ${linha.codigo === "14" ? 'font-black text-slate-900 text-lg uppercase' : ''}`}>
                                            {linha.descricao}
                                        </td>
                                        <td className={`py-3 text-right font-mono ${linha.tipo === 'TOTAL' ? 'font-bold text-slate-900' : 'text-rose-600'} ${linha.codigo === "14" ? 'font-black text-slate-900 text-lg' : ''}`}>
                                            {linha.tipo === 'SUBTRACAO' && linha.valor > 0 ? '-' : ''} {formatCurrency(linha.valor)}
                                        </td>
                                        <td className={`py-3 text-right font-mono text-xs ${linha.tipo === 'TOTAL' ? 'font-bold text-slate-700' : 'text-slate-400'} ${linha.codigo === "14" ? 'font-bold text-slate-700 text-sm' : ''}`}>
                                            {linha.percentual_receita}%
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {/* D. Detalhamento expansível */}
                    <div className="bg-white border border-slate-200 shadow-sm p-4 sm:p-8">
                        <h2 className="text-xl font-bold text-slate-900 mb-6 border-b border-slate-100 pb-4">Análise Detalhada das Despesas</h2>

                        <div className="space-y-4">
                            {dre.grupos_detalhados.map((grupo: import('@/services/api').DREGrupo) => (
                                <div key={grupo.grupo_contabil} className="border border-slate-200 rounded-lg overflow-hidden">
                                    <button
                                        onClick={() => toggleGroup(grupo.grupo_contabil)}
                                        className="w-full bg-slate-50 hover:bg-slate-100 transition p-4 flex items-center justify-between font-semibold text-slate-800"
                                    >
                                        <div className="flex items-center gap-3">
                                            {expandedGroups[grupo.grupo_contabil] ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                                            {grupo.descricao}
                                        </div>
                                        <span className="font-mono">{formatCurrency(grupo.total)}</span>
                                    </button>

                                    {expandedGroups[grupo.grupo_contabil] && (
                                        <div className="bg-white p-4 space-y-4 border-t border-slate-200">
                                            {grupo.categorias.length === 0 ? (
                                                <p className="text-slate-500 text-sm italic">Nenhum lançamento neste grupo.</p>
                                            ) : grupo.categorias.map((cat: import('@/services/api').DRECategoria) => (
                                                <div key={cat.categoria_id} className="border border-slate-100 rounded-md">
                                                    <button
                                                        onClick={() => toggleCat(`${grupo.grupo_contabil}-${cat.categoria_id}`)}
                                                        className="w-full bg-slate-50/50 hover:bg-slate-50 transition p-3 flex items-center justify-between text-sm font-medium text-slate-700"
                                                    >
                                                        <div className="flex items-center gap-2">
                                                            {expandedCats[`${grupo.grupo_contabil}-${cat.categoria_id}`] ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                                                            {cat.categoria_nome} <span className="text-slate-400 font-normal text-xs">({cat.quantidade_lancamentos} itens)</span>
                                                        </div>
                                                        <span className="font-mono">{formatCurrency(cat.total)}</span>
                                                    </button>

                                                    {expandedCats[`${grupo.grupo_contabil}-${cat.categoria_id}`] && (
                                                        <div className="p-3 bg-white border-t border-slate-100 overflow-x-auto">
                                                            <table className="w-full text-xs text-left min-w-[500px]">
                                                                <thead className="text-slate-400 uppercase font-semibold">
                                                                    <tr>
                                                                        <th className="pb-2 w-[15%]">Data</th>
                                                                        <th className="pb-2 w-[40%]">Descrição</th>
                                                                        <th className="pb-2 w-[30%]">Origem/Fornecedor</th>
                                                                        <th className="pb-2 text-right w-[15%]">Valor</th>
                                                                    </tr>
                                                                </thead>
                                                                <tbody className="divide-y divide-slate-50">
                                                                    {cat.lancamentos.map((lanc: import('@/services/api').DRELancamento, idx: number) => (
                                                                        <tr key={idx} className="hover:bg-slate-50 transition">
                                                                            <td className="py-2 text-slate-500 font-mono">{lanc.data_transacao}</td>
                                                                            <td className="py-2 text-slate-700 font-medium">{lanc.descricao}</td>
                                                                            <td className="py-2 text-slate-500">
                                                                                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${lanc.tipo_origem === 'RATEIO' ? 'bg-indigo-50 text-indigo-700' : 'bg-slate-100 text-slate-600'}`}>
                                                                                    {lanc.tipo_origem}
                                                                                </span>
                                                                                {lanc.fornecedor_nome && <span className="ml-2">{lanc.fornecedor_nome}</span>}
                                                                            </td>
                                                                            <td className="py-2 text-right font-mono text-slate-900">{formatCurrency(lanc.valor)}</td>
                                                                        </tr>
                                                                    ))}
                                                                </tbody>
                                                            </table>
                                                        </div>
                                                    )}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>

                    <div className="text-center text-xs text-slate-400 pt-6">
                        <p>Documento gerado automaticamente pelo Sistema Financeiro.</p>
                        <p>Os dados refletem o regime de caixa na data de emissão.</p>
                    </div>
                </div>
            ) : (
                <div className="p-6 bg-slate-50 border border-slate-200 text-slate-500 rounded-lg text-center font-medium">
                    Nenhum dado encontrado para o período ({mes}/{ano}).
                </div>
            )}
        </main>
    );
}
