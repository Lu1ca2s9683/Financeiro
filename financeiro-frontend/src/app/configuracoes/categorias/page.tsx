'use client';

import { useEffect, useState } from 'react';
import { api, Categoria } from '@/services/api';
import Link from 'next/link';
import { ArrowLeft, Plus, CheckCircle2 } from 'lucide-react';

export default function CategoriasPage() {
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Avoid race condition by ensuring token is available
    const token = localStorage.getItem('financeiro_token');
    if (!token) {
      setLoading(false);
      return;
    }

    api.getCategorias()
      .then(setCategorias)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="p-4 sm:p-8 space-y-6 animate-enter">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3 sm:gap-4 w-full sm:w-auto">
          <Link href="/configuracoes" className="p-2 hover:bg-slate-100 rounded-lg transition-colors shrink-0">
            <ArrowLeft size={20} className="text-slate-500" />
          </Link>
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-slate-900">Categorias</h1>
            <p className="text-slate-500 text-sm">Gestão do plano de contas</p>
          </div>
        </div>
        <button
          className="w-full sm:w-auto bg-indigo-600 text-white px-4 py-3 sm:py-2 rounded-lg flex items-center justify-center gap-2 hover:bg-indigo-700 transition shadow-sm disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm sm:text-base shrink-0"
          disabled={loading || !localStorage.getItem('financeiro_token')}
          onClick={async () => {
            try {
              // Basic example to demonstrate the fix, actual implementation might open a modal
              const nome = prompt("Nome da Categoria:");
              if (!nome) return;
              setLoading(true);
              await api.createCategoria(nome);
              const updated = await api.getCategorias();
              setCategorias(updated);
            } catch (err) {
              alert("Erro ao criar categoria: " + (err as Error).message);
            } finally {
              setLoading(false);
            }
          }}
        >
          <Plus size={18} /> Nova Categoria
        </button>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-x-auto w-full">
        {loading ? (
          <div className="p-8 text-center text-slate-500">Carregando...</div>
        ) : (
          <table className="w-full text-left text-sm min-w-[500px]">
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 uppercase text-xs font-semibold">
              <tr>
                <th className="px-6 py-4">ID</th>
                <th className="px-6 py-4">Nome da Categoria</th>
                <th className="px-6 py-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {categorias.map((cat) => (
                <tr key={cat.id} className="hover:bg-slate-50 transition">
                  <td className="px-6 py-4 font-mono text-slate-400">#{cat.id}</td>
                  <td className="px-6 py-4 font-medium text-slate-900">{cat.nome}</td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-100">
                      <CheckCircle2 size={12} /> Ativa
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}