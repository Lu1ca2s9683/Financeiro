'use client';

import { useState, useEffect } from 'react';
import { api } from '@/services/api'; // Certifique-se que src/services/api.ts existe
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Save, AlertCircle } from 'lucide-react';

export default function NovaDespesaPage() {
  const router = useRouter();
  const [categorias, setCategorias] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Estado do formulário
  const [form, setForm] = useState({
    descricao: '',
    loja_id: 1, // Fixo por enquanto
    categoria_id: '',
    valor: '',
    data_competencia: '2025-12-01', // Data default segura para testes
    data_vencimento: '2025-12-10'
  });

  useEffect(() => {
    // Carregamento seguro das categorias
    api.getCategorias()
      .then(setCategorias)
      .catch(err => {
        console.error("Falha ao carregar categorias:", err);
        setErrorMsg("Não foi possível carregar as categorias. Verifique a conexão com o backend.");
      });
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');

    try {
      // Validação básica antes de enviar
      if (!form.categoria_id) {
        throw new Error("Selecione uma categoria.");
      }

      const valorNumerico = parseFloat(form.valor.replace(',', '.'));
      if (isNaN(valorNumerico)) {
        throw new Error("Valor inválido.");
      }

      await api.createDespesa({
        ...form,
        categoria_id: Number(form.categoria_id), // Converte para número
        valor: valorNumerico
      });
      
      alert('Despesa salva com sucesso!');
      router.push('/despesas');
    } catch (error: any) {
      console.error(error);
      setErrorMsg(error.message || "Erro desconhecido ao salvar.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="p-8 max-w-3xl mx-auto">
      <Link href="/despesas" className="flex items-center gap-2 text-slate-500 hover:text-slate-800 mb-6 text-sm font-medium">
        <ArrowLeft size={16} /> Voltar para listagem
      </Link>

      <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
        <h1 className="text-xl font-bold text-slate-900 mb-6">Nova Despesa</h1>
        
        {errorMsg && (
          <div className="mb-6 p-4 bg-red-50 text-red-700 border border-red-200 rounded-lg flex items-center gap-2 text-sm">
            <AlertCircle size={16} />
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Descrição</label>
            <input 
              required
              type="text" 
              className="w-full border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="Ex: Aluguel Dezembro"
              value={form.descricao}
              onChange={e => setForm({...form, descricao: e.target.value})}
            />
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Valor (R$)</label>
              <input 
                required
                type="number" 
                step="0.01"
                className="w-full border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="0.00"
                value={form.valor}
                onChange={e => setForm({...form, valor: e.target.value})}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Categoria</label>
              <select 
                required
                className="w-full border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
                value={form.categoria_id}
                onChange={e => setForm({...form, categoria_id: e.target.value})}
              >
                <option value="">Selecione...</option>
                {categorias.map(cat => (
                  <option key={cat.id} value={cat.id}>{cat.nome}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Competência (Mês/Ref)</label>
              <input 
                required
                type="date" 
                className="w-full border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
                value={form.data_competencia}
                onChange={e => setForm({...form, data_competencia: e.target.value})}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Vencimento</label>
              <input 
                required
                type="date" 
                className="w-full border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
                value={form.data_vencimento}
                onChange={e => setForm({...form, data_vencimento: e.target.value})}
              />
            </div>
          </div>

          <div className="pt-4 border-t border-slate-100 flex justify-end">
             <button 
               type="submit"
               disabled={loading}
               className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700 transition flex items-center gap-2 disabled:opacity-50"
             >
               <Save size={18} />
               {loading ? 'Salvando...' : 'Salvar Lançamento'}
             </button>
          </div>

        </form>
      </div>
    </main>
  );
}