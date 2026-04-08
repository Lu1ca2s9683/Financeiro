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
          onClick={() => {
            const tr = document.getElementById("inline-create-cat");
            if (tr) tr.style.display = "table-row";
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
                <th className="px-6 py-4">Grupo Contábil</th>
                <th className="px-6 py-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              <tr id="inline-create-cat" style={{ display: 'none' }} className="bg-indigo-50/50">
                <td className="px-6 py-4 text-xs font-mono text-indigo-400">NOVA</td>
                <td className="px-6 py-4">
                  <input
                    type="text"
                    id="new-cat-nome"
                    className="border border-indigo-200 rounded p-1 w-full text-sm outline-none focus:ring-2 focus:ring-indigo-500"
                    placeholder="Nome da categoria"
                  />
                </td>
                <td className="px-6 py-4">
                  <select
                    id="new-cat-grupo"
                    className="border border-indigo-200 rounded p-1 w-full text-sm outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                  >
                    <option value="">Selecione o Grupo...</option>
                    <option value="IMPOSTOS">Impostos (Deduções)</option>
                    <option value="CUSTOS">Custos (Serviços/Produtos)</option>
                    <option value="PESSOAL">Despesas com Pessoal</option>
                    <option value="ADMINISTRATIVA">Despesas Administrativas</option>
                    <option value="MARKETING">Vendas e Marketing</option>
                    <option value="FINANCEIRA">Despesas Financeiras</option>
                  </select>
                </td>
                <td className="px-6 py-4 flex gap-2">
                  <button
                    className="bg-indigo-600 text-white px-3 py-1 rounded shadow-sm text-xs font-bold hover:bg-indigo-700"
                    onClick={async () => {
                      const nomeInput = document.getElementById("new-cat-nome") as HTMLInputElement;
                      const grupoInput = document.getElementById("new-cat-grupo") as HTMLSelectElement;
                      if (!nomeInput.value || !grupoInput.value) return alert("Preencha nome e grupo contábil!");

                      setLoading(true);
                      try {
                        await api.createCategoria(nomeInput.value, grupoInput.value);
                        nomeInput.value = "";
                        grupoInput.value = "";
                        document.getElementById("inline-create-cat")!.style.display = "none";
                        const updated = await api.getCategorias();
                        setCategorias(updated);
                      } catch(e: any) {
                        alert("Erro: " + e.message);
                      } finally {
                        setLoading(false);
                      }
                    }}
                  >
                    Salvar
                  </button>
                  <button
                    className="bg-slate-200 text-slate-700 px-3 py-1 rounded shadow-sm text-xs font-bold hover:bg-slate-300"
                    onClick={() => {
                      document.getElementById("inline-create-cat")!.style.display = "none";
                    }}
                  >
                    Cancelar
                  </button>
                </td>
              </tr>
              {categorias.map((cat) => (
                <tr key={cat.id} className="hover:bg-slate-50 transition">
                  <td className="px-6 py-4 font-mono text-slate-400">#{cat.id}</td>
                  <td className="px-6 py-4 font-medium text-slate-900">{cat.nome}</td>
                  <td className="px-6 py-4 text-slate-600 text-xs font-bold tracking-wider">{cat.grupo_contabil}</td>
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