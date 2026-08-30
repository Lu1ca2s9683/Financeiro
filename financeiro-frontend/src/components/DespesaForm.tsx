/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars, react-hooks/exhaustive-deps, react-hooks/set-state-in-effect, @typescript-eslint/no-require-imports */
import { useState, useEffect } from 'react';
import { api, Categoria, DespesaDetail, VendedorAtivo } from '@/services/api';
import { Save, AlertCircle } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { centsToDecimalString, formatCents, parseMoneyToCents } from '@/utils/money';

interface DespesaFormProps {
  initialData?: DespesaDetail;
  onSuccess: () => void;
  onCancel?: () => void;
}

interface RateioForm {
  id?: number;
  descricao: string;
  valor: string;
  categoria_id: string;
  vendedor_id_externo: string;
  vendedor_nome_snapshot?: string | null;
}

export function DespesaForm({ initialData, onSuccess, onCancel }: DespesaFormProps) {
  const { activeLoja } = useAuth();
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [vendedores, setVendedores] = useState<VendedorAtivo[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const [rateios, setRateios] = useState<RateioForm[]>([]);
  const [form, setForm] = useState({
    descricao: '',
    categoria_id: '',
    valor: '',
    data_competencia: (() => {
      if (typeof window !== 'undefined') {
        const urlParams = new URLSearchParams(window.location.search);
        const mes = urlParams.get('mes');
        const ano = urlParams.get('ano');
        if (mes && ano) {
          const m = mes.padStart(2, '0');
          return `${ano}-${m}-01`;
        }
      }
      return new Date().toISOString().slice(0, 10);
    })(),
    data_transacao: new Date().toISOString().slice(0, 10),
    vendedor_id_externo: '',
  });

  useEffect(() => {
    if (initialData) {
      setForm({
        descricao: initialData.descricao,
        categoria_id: initialData.categoria ? String(initialData.categoria.id) : '',
        valor: String(initialData.valor_bruto),
        data_competencia: initialData.data_competencia,
        data_transacao: initialData.data_transacao || new Date().toISOString().slice(0, 10),
        vendedor_id_externo: initialData.vendedor_id_externo
          ? String(initialData.vendedor_id_externo)
          : '',
      });
      if (initialData.splits) {
          setRateios(initialData.splits.map(s => ({
            ...s,
            valor: String(s.valor),
            categoria_id: s.categoria_id ? String(s.categoria_id) : '',
            vendedor_id_externo: s.vendedor_id_externo
              ? String(s.vendedor_id_externo)
              : '',
          })));
      }
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

  useEffect(() => {
    if (!activeLoja?.id) {
      setVendedores([]);
      return;
    }
    api.getVendedoresAtivos(activeLoja.id)
      .then(setVendedores)
      .catch(err => {
        console.error("Falha ao carregar vendedores:", err);
        setErrorMsg("Não foi possível carregar os vendedores ativos.");
      });
  }, [activeLoja?.id]);

  const categoriaPrincipal = categorias.find(
    categoria => String(categoria.id) === form.categoria_id
  );
  const valorCentavos = parseMoneyToCents(form.valor);
  const descontoCentavos = initialData
    ? (parseMoneyToCents(initialData.valor_desconto) ?? 0)
    : 0;
  const acrescimoCentavos = initialData
    ? (parseMoneyToCents(initialData.valor_acrescimo) ?? 0)
    : 0;
  const valorLiquidoAlvoCentavos = valorCentavos === null
    ? null
    : valorCentavos - descontoCentavos + acrescimoCentavos;
  const rateiosCentavos = rateios.map(rateio => parseMoneyToCents(rateio.valor));
  const totalRateadoCentavos = rateiosCentavos.reduce<number>(
    (total, valor) => total + (valor ?? 0),
    0
  );
  const saldoRateioCentavos = (valorLiquidoAlvoCentavos ?? 0) - totalRateadoCentavos;
  const rateioValido = rateios.length === 0 || (
    valorLiquidoAlvoCentavos !== null
    && rateiosCentavos.every(valor => valor !== null && valor > 0)
    && saldoRateioCentavos === 0
  );
  const isOfx = initialData?.origem_lancamento === 'OFX';

  const categoriaEhPessoal = (categoriaId: string, fallbackPrincipal = false) => {
    const categoria = categorias.find(item => String(item.id) === categoriaId)
      || (fallbackPrincipal ? categoriaPrincipal : undefined);
    return categoria?.grupo_contabil === 'PESSOAL';
  };

  const opcoesVendedor = (idAtual: string, nomeSnapshot?: string | null) => {
    const manterSnapshotHistorico = Boolean(idAtual && nomeSnapshot);
    return (
      <>
        <option value="">Sem vendedor</option>
        {manterSnapshotHistorico && (
          <option value={idAtual}>{nomeSnapshot} (histórico)</option>
        )}
        {vendedores
          .filter(vendedor => !(
            manterSnapshotHistorico && String(vendedor.id) === idAtual
          ))
          .map(vendedor => (
          <option key={vendedor.id} value={vendedor.id}>{vendedor.nome}</option>
        ))}
      </>
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg('');

    try {
      if (!form.categoria_id) throw new Error("Selecione uma categoria.");

      if (valorCentavos === null || valorCentavos <= 0) throw new Error("Valor inválido.");
      if (!rateioValido) throw new Error("O rateio deve consumir exatamente o valor da despesa.");

      const payload = {
        descricao: form.descricao,
        categoria_id: Number(form.categoria_id),
        valor: centsToDecimalString(valorCentavos),
        data_competencia: form.data_competencia,
        data_transacao: form.data_transacao,
        vendedor_id_externo: rateios.length === 0 && form.vendedor_id_externo
          ? Number(form.vendedor_id_externo)
          : null,
        rateios: rateios.map((rateio, index) => ({
          id: rateio.id,
          descricao: rateio.descricao,
          valor: centsToDecimalString(rateiosCentavos[index] as number),
          categoria_id: rateio.categoria_id ? Number(rateio.categoria_id) : undefined,
          vendedor_id_externo: rateio.vendedor_id_externo
            ? Number(rateio.vendedor_id_externo)
            : null,
        })),
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
          className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500 placeholder-slate-400"
          placeholder="Ex: Aluguel Dezembro"
          value={form.descricao}
          onChange={e => setForm({...form, descricao: e.target.value})}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Valor (R$)</label>
          <input
            required
            disabled={isOfx}
            type="number"
            step="0.01"
            className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500 placeholder-slate-400 disabled:bg-slate-100 disabled:text-slate-500"
            placeholder="0.00"
            value={form.valor}
            onChange={e => setForm({...form, valor: e.target.value})}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Categoria Contábil</label>
          <select
            required
            className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
            value={form.categoria_id}
            onChange={e => {
              const novaCategoria = categorias.find(cat => String(cat.id) === e.target.value);
              setRateios(rateios.map(rateio => {
                const categoriaRateio = rateio.categoria_id
                  ? categorias.find(cat => String(cat.id) === rateio.categoria_id)
                  : novaCategoria;
                return categoriaRateio?.grupo_contabil === 'PESSOAL'
                  ? rateio
                  : {...rateio, vendedor_id_externo: ''};
              }));
              setForm({
                ...form,
                categoria_id: e.target.value,
                vendedor_id_externo: novaCategoria?.grupo_contabil === 'PESSOAL'
                  ? form.vendedor_id_externo
                  : '',
              });
            }}
          >
            <option value="">Selecione a categoria...</option>
            {categorias.map(cat => (
              <option key={cat.id} value={cat.id}>
                {cat.nome} ({cat.grupo_contabil})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Competência (Mês/Ref)</label>
          <input
            required
            type="date"
            className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
            value={form.data_competencia}
            onChange={e => setForm({...form, data_competencia: e.target.value})}
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Data Transação</label>
          <input
            required
            disabled={isOfx}
            type="date"
            className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-slate-100 disabled:text-slate-500"
            value={form.data_transacao}
            onChange={e => setForm({...form, data_transacao: e.target.value})}
          />
        </div>
      </div>

      {isOfx && (
        <p className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-800">
          Estes dados vieram do extrato bancário. O valor e a data da transação não podem ser editados.
        </p>
      )}

      {categoriaPrincipal?.grupo_contabil === 'PESSOAL' && rateios.length === 0 && (
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Associar vendedor</label>
          <select
            className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
            value={form.vendedor_id_externo}
            onChange={e => setForm({...form, vendedor_id_externo: e.target.value})}
          >
            {opcoesVendedor(
              form.vendedor_id_externo,
              initialData?.vendedor_nome_snapshot
            )}
          </select>
          <p className="mt-1 text-xs text-slate-500">A associação é analítica e não altera a categoria contábil.</p>
        </div>
      )}

      <div className="pt-4 border-t border-slate-100">
        <h3 className="text-sm font-medium text-slate-700 mb-4">Rateio (Divisão de Despesa)</h3>
        {rateios.map((r, index) => (
            <div key={index} className="grid grid-cols-1 sm:grid-cols-5 gap-4 mb-4">
                <input
                    type="text"
                    placeholder="Descrição do rateio"
                    className="sm:col-span-2 w-full bg-white border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
                    value={r.descricao}
                    onChange={e => {
                        const newRateios = [...rateios];
                        newRateios[index].descricao = e.target.value;
                        setRateios(newRateios);
                    }}
                />
                <input
                    type="number"
                    step="0.01"
                    placeholder="Valor"
                    className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
                    value={r.valor}
                    onChange={e => {
                        const newRateios = [...rateios];
                        newRateios[index].valor = e.target.value;
                        setRateios(newRateios);
                    }}
                />
                <select
                    className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
                    value={r.categoria_id}
                    onChange={e => {
                        const newRateios = [...rateios];
                        newRateios[index] = {
                          ...newRateios[index],
                          categoria_id: e.target.value,
                          vendedor_id_externo: categoriaEhPessoal(e.target.value, true)
                            ? newRateios[index].vendedor_id_externo
                            : '',
                        };
                        setRateios(newRateios);
                    }}
                >
                    <option value="">(Usar principal)</option>
                    {categorias.map(cat => (
                        <option key={cat.id} value={cat.id}>{cat.nome}</option>
                    ))}
                </select>
                <div className="flex gap-2">
                    {categoriaEhPessoal(r.categoria_id, true) ? (
                    <select
                        className="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500"
                        aria-label={`Vendedor do rateio ${index + 1}`}
                        value={r.vendedor_id_externo}
                        onChange={e => {
                            const newRateios = [...rateios];
                            newRateios[index].vendedor_id_externo = e.target.value;
                            setRateios(newRateios);
                        }}
                    >
                        {opcoesVendedor(r.vendedor_id_externo, r.vendedor_nome_snapshot)}
                    </select>
                    ) : <span className="w-full px-3 py-2 text-xs text-slate-400">Sem vendedor</span>}
                    <button
                        type="button"
                        onClick={() => {
                            const newRateios = [...rateios];
                            newRateios.splice(index, 1);
                            setRateios(newRateios);
                        }}
                        className="p-2 text-rose-500 bg-rose-50 rounded"
                    >
                        X
                    </button>
                </div>
            </div>
        ))}
        <button
            type="button"
            onClick={() => {
              setForm({...form, vendedor_id_externo: ''});
              setRateios([...rateios, {
                descricao: '',
                valor: '',
                categoria_id: '',
                vendedor_id_externo: '',
              }]);
            }}
            className="text-sm text-indigo-600 hover:text-indigo-800 font-medium"
        >
            + Adicionar linha de rateio
        </button>
        {rateios.length > 0 && (
          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm space-y-2">
            <div className="flex justify-between"><span>Valor líquido da despesa</span><strong>{formatCents(valorLiquidoAlvoCentavos ?? 0)}</strong></div>
            <div className="flex justify-between"><span>Total rateado</span><strong>{formatCents(totalRateadoCentavos)}</strong></div>
            <div className={`flex justify-between border-t border-slate-200 pt-2 ${saldoRateioCentavos === 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
              <span>Saldo a ratear</span><strong>{formatCents(saldoRateioCentavos)}</strong>
            </div>
          </div>
        )}
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
           disabled={loading || !rateioValido}
           className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700 transition flex items-center gap-2 disabled:opacity-50"
         >
           <Save size={18} />
           {loading ? 'Salvando...' : 'Salvar'}
         </button>
      </div>
    </form>
  );
}
