import sys

content = """'use client';
import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/services/api';
import { useDateFilter } from '@/contexts/DateFilterContext';
import { Download } from 'lucide-react';
import { PeriodSelector } from '@/components/PeriodSelector';

export default function DreGerencialPage() {
    const { activeLoja } = useAuth();
    const { mes, ano } = useDateFilter();
    const [fechamento, setFechamento] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!activeLoja) return;
        setLoading(true);
        api.getFechamento(activeLoja.id, mes, ano)
           .then(setFechamento)
           .catch(console.error)
           .finally(() => setLoading(false));
    }, [activeLoja, mes, ano]);

    if (!activeLoja) return null;

    const formatCurrency = (val: number | string) => {
        return Number(val || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
    };

    return (
        <main className="p-8 space-y-8 animate-enter max-w-5xl mx-auto font-sans">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-end border-b-2 border-slate-900 pb-4 gap-4">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900 tracking-tight uppercase">Demonstrativo do Resultado do Exercício</h1>
                    <p className="text-slate-500 mt-1 font-medium">DRE Gerencial Consolidado (Regime de Caixa)</p>
                </div>
                <div className="flex items-center gap-4">
                    <PeriodSelector />
                    <button className="flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900 transition-colors border border-slate-300 px-4 py-2 rounded-md shadow-sm h-[40px]">
                        <Download size={16} /> PDF
                    </button>
                </div>
            </div>

            {loading ? (
                <div className="flex justify-center p-20 text-slate-400">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900"></div>
                </div>
            ) : fechamento ? (
                <div className="bg-white border border-slate-200 shadow-sm p-8">
                    <table className="w-full text-left text-sm table-fixed border-collapse">
                        <colgroup>
                            <col className="w-3/4" />
                            <col className="w-1/4" />
                        </colgroup>
                        <tbody className="divide-y divide-slate-100">
                            <tr className="border-b-2 border-slate-200">
                                <td className="py-3 font-bold text-slate-900 uppercase text-xs tracking-wider">Descrição</td>
                                <td className="py-3 font-bold text-right text-slate-900 uppercase text-xs tracking-wider">Valor (R$)</td>
                            </tr>

                            <tr>
                                <td className="py-3 font-bold text-slate-900 text-base">1. RECEITA BRUTA OPERACIONAL</td>
                                <td className="py-3 font-bold text-right font-mono text-base text-slate-900">
                                    {formatCurrency(fechamento.receita_bruta)}
                                </td>
                            </tr>
                            <tr>
                                <td className="py-2 text-slate-600 pl-6 border-l-2 border-slate-100">(-) Deduções e Impostos sobre Vendas</td>
                                <td className="py-2 text-slate-600 text-right font-mono">
                                    {formatCurrency(fechamento.impostos)}
                                </td>
                            </tr>

                            <tr className="border-t border-slate-200 bg-slate-50">
                                <td className="py-3 font-bold text-slate-900 text-base pl-2">2. RECEITA LÍQUIDA OPERACIONAL</td>
                                <td className="py-3 font-bold text-right font-mono text-base text-slate-900">
                                    {formatCurrency(fechamento.receita_liquida)}
                                </td>
                            </tr>
                            <tr>
                                <td className="py-2 text-slate-600 pl-6 border-l-2 border-slate-100">(-) Custos de Produtos Vendidos / Serviços Prestados</td>
                                <td className="py-2 text-slate-600 text-right font-mono">
                                    {formatCurrency(fechamento.custos_produtos)}
                                </td>
                            </tr>

                            <tr className="border-t border-slate-200 bg-slate-50">
                                <td className="py-3 font-bold text-slate-900 text-base pl-2">3. LUCRO BRUTO</td>
                                <td className="py-3 font-bold text-right font-mono text-base text-slate-900">
                                    {formatCurrency(fechamento.lucro_bruto)}
                                </td>
                            </tr>
                            <tr>
                                <td className="py-2 text-slate-600 pl-6 border-l-2 border-slate-100">(-) Despesas Operacionais</td>
                                <td className="py-2 text-slate-600 text-right font-mono">
                                    {formatCurrency(fechamento.despesas_operacionais)}
                                </td>
                            </tr>

                            <tr className="border-t border-slate-200 bg-slate-50">
                                <td className="py-3 font-bold text-slate-900 text-base pl-2">4. RESULTADO OPERACIONAL ANTES DO RESULTADO FINANCEIRO</td>
                                <td className="py-3 font-bold text-right font-mono text-base text-slate-900">
                                    {formatCurrency(fechamento.resultado_operacional)}
                                </td>
                            </tr>
                            <tr>
                                <td className="py-2 text-slate-600 pl-6 border-l-2 border-slate-100">(-) Despesas Financeiras e Taxas de Cartão</td>
                                <td className="py-2 text-slate-600 text-right font-mono">
                                    {formatCurrency(Number(fechamento.total_taxas || 0) + Number(fechamento.despesas_financeiras || 0))}
                                </td>
                            </tr>

                            <tr className="border-t-4 border-slate-900 bg-slate-100">
                                <td className="py-4 font-black text-slate-900 text-lg uppercase">5. RESULTADO LÍQUIDO DO EXERCÍCIO</td>
                                <td className="py-4 font-black text-right font-mono text-lg text-slate-900">
                                    {formatCurrency(fechamento.lucro_liquido)}
                                </td>
                            </tr>
                        </tbody>
                    </table>

                    <div className="mt-12 text-center text-xs text-slate-400 border-t border-slate-100 pt-6">
                        <p>Documento gerado automaticamente pelo Sistema Financeiro.</p>
                        <p>Os dados refletem o regime de caixa na data de emissão.</p>
                    </div>
                </div>
            ) : (
                <div className="p-6 bg-slate-50 border border-slate-200 text-slate-500 rounded-lg text-center font-medium">
                    Nenhum dado encontrado para o período ({mes}/{ano}). Certifique-se de realizar o fechamento do mês.
                </div>
            )}
        </main>
    );
}
"""
filepath = './financeiro-frontend/src/app/relatorios/dre/page.tsx'
with open(filepath, 'w') as f:
    f.write(content)
