/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars, react-hooks/exhaustive-deps, react-hooks/set-state-in-effect, @typescript-eslint/no-require-imports */
'use client';
import { useState, useMemo, useEffect } from 'react';
import { UploadCloud } from 'lucide-react';
import { api, ContaBancaria, ExtratoItem } from '@/services/api';
import { useFinanceiro } from '@/contexts/FinanceiroContext';

export default function ConferenciaPage() {
    const { lojaId } = useFinanceiro();
    const [file, setFile] = useState<File | null>(null);
    const [extrato, setExtrato] = useState<ExtratoItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [contas, setContas] = useState<ContaBancaria[]>([]);
    const [contaOrigemId, setContaOrigemId] = useState('');

    useEffect(() => {
        if (!lojaId) return;
        api.getContasBancarias()
            .then(data => setContas(data.filter(conta => conta.ativo)))
            .catch(console.error);
        setContaOrigemId('');
        setExtrato([]);
    }, [lojaId]);

    const handleImport = async () => {
        if (!file || !lojaId || !contaOrigemId) return;
        setLoading(true);
        try {
            const data = await api.importarExtratoDespesas(
                lojaId,
                Number(contaOrigemId),
                file
            );
            // Regra de Negócio: Mostrar apenas ENTRADAS na tela de conferência
            setExtrato(data.filter((item) => item.tipo === 'ENTRADA'));
        } catch (e) {
            console.error(e);
            alert("Erro ao importar arquivo");
        } finally {
            setLoading(false);
        }
    };

    const totalEntradasExtrato = useMemo(() => {
        return extrato.reduce((acc, item) => acc + Number(item.valor), 0);
    }, [extrato]);

    return (
        <main className="p-8 space-y-6 animate-enter flex flex-col min-h-screen">
            <h1 className="text-2xl font-bold text-slate-900">Conferência / Conciliação Bancária</h1>

            {/* Painel de Balanço (Dashboard de Conciliação) */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-center">
                    <span className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-1">Entradas na Conta (Extrato)</span>
                    <span className="text-3xl font-bold text-emerald-600 font-mono">
                        {totalEntradasExtrato.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                    </span>
                </div>

                <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-center">
                    <span className="text-sm font-semibold text-slate-500 uppercase tracking-wider mb-1">Vendas no Sistema</span>
                    <span className="text-sm font-semibold text-slate-500">Dados de vendas não disponíveis nesta fase.</span>
                </div>

                <div className="p-6 rounded-xl border shadow-sm flex flex-col justify-center bg-slate-50 border-slate-200">
                    <span className="text-sm font-semibold uppercase tracking-wider mb-1 text-slate-600">Diferença (Consolidação)</span>
                    <span className="text-sm font-semibold text-slate-500">Indisponível sem integração real de vendas.</span>
                </div>
            </div>

            <div className="flex gap-4 items-center bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                <select
                    aria-label="Conta bancária do extrato"
                    value={contaOrigemId}
                    onChange={event => setContaOrigemId(event.target.value)}
                    className="border border-slate-300 rounded-lg px-3 py-2"
                >
                    <option value="">Selecione a conta...</option>
                    {contas.map(conta => (
                        <option key={conta.id} value={conta.id}>{conta.nome}</option>
                    ))}
                </select>
                <input
                    type="file"
                    accept=".ofx,.ofc"
                    onChange={e => setFile(e.target.files?.[0] || null)}
                    className="file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                />
                <button
                    onClick={handleImport}
                    disabled={!file || !contaOrigemId || loading}
                    className="bg-indigo-600 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 hover:bg-indigo-700 transition disabled:opacity-50"
                >
                    <UploadCloud size={18} /> {loading ? 'Lendo...' : 'Ler Extrato'}
                </button>
            </div>

            <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-6 min-h-0">
                {/* Coluna Esquerda: Extrato */}
                <div className="bg-white border border-slate-200 rounded-xl shadow-sm flex flex-col min-h-[500px]">
                    <div className="p-4 border-b border-slate-100 bg-slate-50 sticky top-0 rounded-t-xl">
                        <h2 className="font-bold text-slate-800">Entradas do Extrato Importado</h2>
                    </div>
                    <div className="overflow-y-auto p-4 space-y-3 flex-1">
                        {extrato.length === 0 ? (
                            <p className="text-slate-400 text-center mt-10">Importe um arquivo OFX/OFC para visualizar as transações.</p>
                        ) : (
                            extrato.map((item, idx) => (
                                <div key={idx} className="flex justify-between items-center p-3 bg-slate-50 rounded-lg border border-slate-100">
                                    <div>
                                        <div className="text-xs text-slate-500 font-mono">{item.data_transacao}</div>
                                        <div className="text-sm font-medium text-slate-800">{item.descricao_original}</div>
                                    </div>
                                    <div className="font-mono font-bold text-emerald-600">
                                        + {Number(item.valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* Coluna Direita: Vendas do Sistema */}
                <div className="bg-white border border-slate-200 rounded-xl shadow-sm flex flex-col min-h-[500px]">
                    <div className="p-4 border-b border-slate-100 bg-slate-50 sticky top-0 rounded-t-xl flex justify-between items-center">
                        <h2 className="font-bold text-slate-800">Vendas (Sistema)</h2>
                        <span className="text-xs text-slate-500">Apenas entradas projetadas</span>
                    </div>
                    <div className="overflow-y-auto p-4 space-y-3 flex-1">
                        <p className="text-slate-400 text-center mt-10">
                            Dados de vendas não disponíveis: nenhuma integração real de conciliação foi implementada.
                        </p>
                    </div>
                </div>
            </div>
        </main>
    );
}
