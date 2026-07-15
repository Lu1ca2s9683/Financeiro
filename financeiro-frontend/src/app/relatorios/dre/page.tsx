'use client';
import { useState, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/services/api';
import { useDateFilter } from '@/contexts/DateFilterContext';
import { DollarSign, TrendingUp, AlertTriangle } from 'lucide-react';

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

    return (
        <main className="p-8 space-y-6 animate-enter max-w-4xl mx-auto">
            <h1 className="text-2xl font-bold text-slate-900">DRE Gerencial (Regime de Caixa)</h1>
            <p className="text-slate-500">Mês de Referência: {mes}/{ano}</p>

            {loading ? (
                <div className="flex justify-center p-12 text-slate-400">Carregando DRE...</div>
            ) : fechamento ? (
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                    <table className="w-full text-left text-sm">
                        <tbody className="divide-y divide-slate-100">
                            <tr className="bg-slate-50">
                                <td className="px-6 py-4 font-bold text-slate-900">1. Receita Bruta (Vendas)</td>
                                <td className="px-6 py-4 font-bold text-right font-mono">
                                    {Number(fechamento.receita_bruta || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                </td>
                            </tr>
                            <tr>
                                <td className="px-6 py-4 text-slate-600 pl-10">- Impostos e Deduções</td>
                                <td className="px-6 py-4 text-rose-600 text-right font-mono">
                                    - {Number(fechamento.impostos || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                </td>
                            </tr>
                            <tr className="bg-slate-50">
                                <td className="px-6 py-4 font-bold text-slate-900">2. Receita Líquida</td>
                                <td className="px-6 py-4 font-bold text-right font-mono text-indigo-600">
                                    {Number(fechamento.receita_liquida || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                </td>
                            </tr>
                            <tr>
                                <td className="px-6 py-4 text-slate-600 pl-10">- Custo dos Produtos/Serviços (CMV)</td>
                                <td className="px-6 py-4 text-rose-600 text-right font-mono">
                                    - {Number(fechamento.custos_produtos || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                </td>
                            </tr>
                            <tr className="bg-slate-50">
                                <td className="px-6 py-4 font-bold text-slate-900">3. Lucro Bruto (Margem de Contribuição)</td>
                                <td className="px-6 py-4 font-bold text-right font-mono text-indigo-600">
                                    {Number(fechamento.lucro_bruto || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                </td>
                            </tr>
                            <tr>
                                <td className="px-6 py-4 text-slate-600 pl-10">- Despesas Operacionais (Administrativas, Pessoal, etc)</td>
                                <td className="px-6 py-4 text-rose-600 text-right font-mono">
                                    - {Number(fechamento.despesas_operacionais || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                </td>
                            </tr>
                            <tr className="bg-slate-50">
                                <td className="px-6 py-4 font-bold text-slate-900">4. Resultado Operacional</td>
                                <td className="px-6 py-4 font-bold text-right font-mono text-indigo-600">
                                    {Number(fechamento.resultado_operacional || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                </td>
                            </tr>
                            <tr>
                                <td className="px-6 py-4 text-slate-600 pl-10">- Taxas e Despesas Financeiras</td>
                                <td className="px-6 py-4 text-rose-600 text-right font-mono">
                                    - {Number((fechamento.total_taxas || 0) + (fechamento.despesas_financeiras || 0)).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                </td>
                            </tr>
                            <tr className="bg-slate-900 text-white">
                                <td className="px-6 py-4 font-bold">5. Resultado Líquido Final</td>
                                <td className="px-6 py-4 font-bold text-right font-mono text-emerald-400 text-lg">
                                    {Number(fechamento.lucro_liquido || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            ) : (
                <div className="p-4 bg-rose-50 text-rose-600 rounded-lg">Não foi possível gerar o DRE para o período selecionado.</div>
            )}
        </main>
    );
}
