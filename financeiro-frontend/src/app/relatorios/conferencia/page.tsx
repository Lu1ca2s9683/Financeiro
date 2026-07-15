'use client';
import { useState } from 'react';
import { UploadCloud, CheckCircle, XCircle } from 'lucide-react';
import { api, ExtratoItem } from '@/services/api';

export default function ConferenciaPage() {
    const [file, setFile] = useState<File | null>(null);
    const [extrato, setExtrato] = useState<ExtratoItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [vendasMock, setVendasMock] = useState<any[]>([
        { id: 1, data: '2024-01-10', valor: 1500.00, descricao: 'Venda de produtos A' },
        { id: 2, data: '2024-01-15', valor: 300.00, descricao: 'Serviço prestado B' }
    ]);

    const handleImport = async () => {
        if (!file) return;
        setLoading(true);
        try {
            const data = await api.importExtrato(file);
            setExtrato(data);
        } catch (e) {
            console.error(e);
            alert("Erro ao importar arquivo");
        } finally {
            setLoading(false);
        }
    };

    return (
        <main className="p-8 space-y-6 animate-enter h-[calc(100vh-64px)] flex flex-col">
            <h1 className="text-2xl font-bold text-slate-900">Conferência / Conciliação Bancária</h1>

            <div className="flex gap-4 items-center bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                <input
                    type="file"
                    accept=".ofx,.ofc"
                    onChange={e => setFile(e.target.files?.[0] || null)}
                    className="file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                />
                <button
                    onClick={handleImport}
                    disabled={!file || loading}
                    className="bg-indigo-600 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 hover:bg-indigo-700 transition disabled:opacity-50"
                >
                    <UploadCloud size={18} /> {loading ? 'Lendo...' : 'Ler Extrato'}
                </button>
            </div>

            <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-6 min-h-0">
                {/* Coluna Esquerda: Extrato */}
                <div className="bg-white border border-slate-200 rounded-xl shadow-sm flex flex-col min-h-0">
                    <div className="p-4 border-b border-slate-100 bg-slate-50 sticky top-0 rounded-t-xl">
                        <h2 className="font-bold text-slate-800">Extrato Importado (Banco)</h2>
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
                                    <div className={`font-mono font-bold ${item.tipo === 'ENTRADA' ? 'text-emerald-600' : 'text-rose-600'}`}>
                                        {item.tipo === 'ENTRADA' ? '+' : '-'} {Number(item.valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>

                {/* Coluna Direita: Vendas do Sistema */}
                <div className="bg-white border border-slate-200 rounded-xl shadow-sm flex flex-col min-h-0">
                    <div className="p-4 border-b border-slate-100 bg-slate-50 sticky top-0 rounded-t-xl flex justify-between items-center">
                        <h2 className="font-bold text-slate-800">Vendas (Sistema)</h2>
                        <span className="text-xs text-slate-500">Apenas entradas projetadas</span>
                    </div>
                    <div className="overflow-y-auto p-4 space-y-3 flex-1">
                        {vendasMock.map(venda => (
                            <div key={venda.id} className="flex justify-between items-center p-3 bg-emerald-50 rounded-lg border border-emerald-100 cursor-pointer hover:bg-emerald-100 transition">
                                <div>
                                    <div className="text-xs text-emerald-600/70 font-mono">{venda.data}</div>
                                    <div className="text-sm font-medium text-emerald-900">{venda.descricao}</div>
                                </div>
                                <div className="font-mono font-bold text-emerald-700">
                                    {Number(venda.valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </main>
    );
}
