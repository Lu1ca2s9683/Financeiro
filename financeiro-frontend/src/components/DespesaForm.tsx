import { useState, useEffect } from 'react';
import { api, DespesaDetail } from '@/services/api';
import { Save, AlertCircle } from 'lucide-react';

interface DespesaFormProps {
  initialData?: DespesaDetail;
  onSuccess: () => void;
  onCancel?: () => void;
}

export function DespesaForm({ initialData, onSuccess, onCancel }: DespesaFormProps) {
  const [categorias, setCategorias] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const [form, setForm] = useState({
    descricao: '',
    loja_id: 1,
    categoria_id: '',
    valor: '',
    data_competencia: new Date().toISOString().slice(0, 10),
    data_vencimento: new Date().toISOString().slice(0, 10)
  });

  useEffect(() => {
    if (initialData) {
      setForm({
        descricao: initialData.descricao,
        loja_id: initialData.loja_id_externo,
        categoria_id: initialData.categoria ? String(initialData.categoria.id) : '',
        valor: String(initialData.valor_bruto),
        data_competencia: initialData.data_competencia,
        data_vencimento: initialData.data_vencimento
      });
    }
  }, [initialData]);

  useEffect(() => {
    api.getCategorias()
      .then(setCategorias)
      .catch(err => {
        console.error("Falha ao carregar categorias:", err);
        setErrorMsg("Não foi possível carregar as categorias.");
      });
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');

    try {
      if (!form.categoria_id) throw new Error("Selecione uma categoria.");

      const valorNumerico = parseFloat(form.valor.replace(',', '.'));
      if (isNaN(valorNumerico)) throw new Error("Valor inválido.");

      const payload = {
        ...form,
        categoria_id: Number(form.categoria_id),
        valor: valorNumerico
      };

      if (initialData) {
        await api.updateDespesa(initialData.id, payload);
      } else {
        await api.createDespesa(payload);
      }

      onSuccess();
    } catch (error: any) {
      console.error(error);
      setErrorMsg(error.message || "Erro desconhecido ao salvar.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {errorMsg && (
        <div className="p-4 bg-red-50 text-red-700 border border-red-200 rounded-lg flex items-center gap-2 text-sm">
          <AlertCircle size={16} />
          {errorMsg}
        </div>
      )}

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

      <div className="pt-4 border-t border-slate-100 flex justify-end gap-3">
         {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="px-4 py-2 border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-50 transition"
            >
              Cancelar
            </button>
         )}
         <button
           type="submit"
           disabled={loading}
           className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700 transition flex items-center gap-2 disabled:opacity-50"
         >
           <Save size={18} />
           {loading ? 'Salvando...' : 'Salvar'}
         </button>
      </div>
    </form>
  );
}
