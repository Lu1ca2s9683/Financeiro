'use client';

import { useEffect, useState } from 'react';
import { api, ContaBancaria } from '@/services/api';
import { useFinanceiro } from '@/contexts/FinanceiroContext';
import { Wallet, Landmark, PiggyBank, Plus, ArrowRightLeft, X } from 'lucide-react';

export default function TesourariaPage() {
  const { lojaId } = useFinanceiro();
  const [contas, setContas] = useState<ContaBancaria[]>([]);
  const [loading, setLoading] = useState(true);

  // Modals state
  const [isContaModalOpen, setIsContaModalOpen] = useState(false);
  const [isTransferModalOpen, setIsTransferModalOpen] = useState(false);

  const fetchContas = async () => {
    setLoading(true);
    try {
      const data = await api.getContasBancarias();
      setContas(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContas();
  }, [lojaId]);

  const fmt = (val: number) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(val);

  return (
    <main className="p-4 sm:p-8 space-y-8 animate-enter max-w-[1600px] mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-200 pb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">Tesouraria</h1>
          <p className="text-slate-500 text-sm mt-1">Gestão de saldos e fluxo de caixa em tempo real</p>
        </div>

        <div className="flex flex-col sm:flex-row items-center gap-3 w-full sm:w-auto">
          <button
            onClick={() => setIsTransferModalOpen(true)}
            className="w-full sm:w-auto bg-indigo-600 text-white px-5 py-2.5 rounded-lg flex items-center justify-center gap-2 hover:bg-indigo-700 transition shadow-sm font-medium"
          >
            <ArrowRightLeft size={18} /> Transferência / Sangria
          </button>
          <button
            onClick={() => setIsContaModalOpen(true)}
            className="w-full sm:w-auto bg-white border border-slate-300 text-slate-700 px-5 py-2.5 rounded-lg flex items-center justify-center gap-2 hover:bg-slate-50 transition shadow-sm font-medium"
          >
            <Plus size={18} /> Nova Conta
          </button>
        </div>
      </div>

      {/* Resumo de Contas (Cards) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading ? (
          [1, 2, 3].map(i => <div key={i} className="h-32 bg-slate-200 rounded-2xl animate-pulse"></div>)
        ) : contas.length === 0 ? (
          <div className="col-span-full p-8 text-center bg-white rounded-2xl border border-slate-200 shadow-sm text-slate-500">
            Nenhuma conta bancária ou caixa cadastrado para esta loja.
          </div>
        ) : (
          contas.map(conta => (
            <div key={conta.id} className="bg-white p-6 rounded-2xl border border-slate-200/60 shadow-sm hover:shadow-md transition-shadow relative overflow-hidden group">
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-slate-50 text-slate-600 rounded-xl border border-slate-100">
                    {conta.tipo === 'CAIXA_FISICO' ? <Wallet size={24} className="text-emerald-600" /> :
                     conta.tipo === 'POUPANCA' ? <PiggyBank size={24} className="text-blue-500" /> :
                     <Landmark size={24} className="text-indigo-600" />}
                  </div>
                  <div>
                    <p className="text-sm font-bold text-slate-900 leading-tight">{conta.nome}</p>
                    <p className="text-xs font-medium text-slate-400 mt-0.5">
                      {conta.tipo.replace('_', ' ')}
                    </p>
                  </div>
                </div>
              </div>
              <div className="mt-6">
                <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold mb-1">Saldo Atual</p>
                <h3 className={`text-3xl font-bold tracking-tight ${conta.saldo_atual < 0 ? 'text-rose-600' : 'text-slate-900'}`}>
                  {fmt(conta.saldo_atual)}
                </h3>
              </div>
              {/* Highlight bar at bottom */}
              <div className={`absolute bottom-0 left-0 h-1 w-full ${
                conta.tipo === 'CAIXA_FISICO' ? 'bg-emerald-500' :
                conta.tipo === 'POUPANCA' ? 'bg-blue-500' : 'bg-indigo-500'
              }`}></div>
            </div>
          ))
        )}
      </div>

      {/* Modal: Nova Conta */}
      {isContaModalOpen && (
        <NovaContaModal
          onClose={() => setIsContaModalOpen(false)}
          onSuccess={() => { setIsContaModalOpen(false); fetchContas(); }}
        />
      )}

      {/* Modal: Transferência */}
      {isTransferModalOpen && (
        <NovaTransferenciaModal
          contas={contas}
          onClose={() => setIsTransferModalOpen(false)}
          onSuccess={() => { setIsTransferModalOpen(false); fetchContas(); }}
        />
      )}
    </main>
  );
}

// Subcomponente: Nova Conta
function NovaContaModal({ onClose, onSuccess }: { onClose: () => void, onSuccess: () => void }) {
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    nome: '',
    tipo: 'CONTA_CORRENTE',
    saldo_inicial: '0.00'
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.createContaBancaria({
        ...form,
        saldo_inicial: parseFloat(form.saldo_inicial.replace(',', '.'))
      });
      onSuccess();
    } catch (err: any) {
      alert("Erro: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="flex justify-between items-center p-6 border-b border-slate-100">
          <h2 className="text-xl font-bold text-slate-900">Nova Conta Bancária</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition p-1"><X size={20}/></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Nome da Conta / Cofre</label>
            <input required type="text" className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500 placeholder-slate-400" placeholder="Ex: Cofre Central" value={form.nome} onChange={e => setForm({...form, nome: e.target.value})} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Tipo de Conta</label>
            <select required className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500" value={form.tipo} onChange={e => setForm({...form, tipo: e.target.value})}>
              <option value="CONTA_CORRENTE">Conta Corrente</option>
              <option value="CAIXA_FISICO">Caixa Físico (Dinheiro)</option>
              <option value="POUPANCA">Poupança</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Saldo Inicial (R$)</label>
            <input required type="number" step="0.01" className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500 placeholder-slate-400" placeholder="0.00" value={form.saldo_inicial} onChange={e => setForm({...form, saldo_inicial: e.target.value})} />
          </div>
          <div className="pt-2 flex justify-end gap-3">
            <button type="button" onClick={onClose} className="px-4 py-2 text-slate-600 hover:bg-slate-100 font-medium rounded-lg transition">Cancelar</button>
            <button type="submit" disabled={loading} className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700 transition disabled:opacity-50">Salvar Conta</button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Subcomponente: Transferencia
function NovaTransferenciaModal({ contas, onClose, onSuccess }: { contas: ContaBancaria[], onClose: () => void, onSuccess: () => void }) {
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    conta_origem_id: '',
    conta_destino_id: '',
    valor: '',
    data_ocorrencia: new Date().toISOString().slice(0, 10),
    descricao: ''
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (form.conta_origem_id === form.conta_destino_id) throw new Error("A origem não pode ser igual ao destino.");

      await api.createTransferencia({
        ...form,
        conta_origem_id: Number(form.conta_origem_id),
        conta_destino_id: Number(form.conta_destino_id),
        valor: parseFloat(form.valor.replace(',', '.'))
      });
      onSuccess();
    } catch (err: any) {
      alert("Erro: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden animate-in zoom-in-95 duration-200">
        <div className="flex justify-between items-center p-6 border-b border-slate-100">
          <h2 className="text-xl font-bold text-slate-900 flex items-center gap-2"><ArrowRightLeft size={20} className="text-indigo-600"/> Nova Transferência</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition p-1"><X size={20}/></button>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-5">

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">De (Origem)</label>
              <select required className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500" value={form.conta_origem_id} onChange={e => setForm({...form, conta_origem_id: e.target.value})}>
                <option value="">Selecione...</option>
                {contas.map(c => <option key={c.id} value={c.id}>{c.nome} (R$ {c.saldo_atual})</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Para (Destino)</label>
              <select required className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500" value={form.conta_destino_id} onChange={e => setForm({...form, conta_destino_id: e.target.value})}>
                <option value="">Selecione...</option>
                {contas.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Valor (R$)</label>
              <input required type="number" step="0.01" className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500 placeholder-slate-400" placeholder="0.00" value={form.valor} onChange={e => setForm({...form, valor: e.target.value})} />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Data</label>
              <input required type="date" className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500" value={form.data_ocorrencia} onChange={e => setForm({...form, data_ocorrencia: e.target.value})} />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Descrição</label>
            <input required type="text" className="w-full bg-white text-slate-900 border border-slate-300 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500 placeholder-slate-400" placeholder="Ex: Sangria do Caixa para o Banco" value={form.descricao} onChange={e => setForm({...form, descricao: e.target.value})} />
          </div>

          <div className="pt-2 flex justify-end gap-3">
            <button type="button" onClick={onClose} className="px-4 py-2 text-slate-600 hover:bg-slate-100 font-medium rounded-lg transition">Cancelar</button>
            <button type="submit" disabled={loading} className="bg-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:bg-indigo-700 transition disabled:opacity-50">Confirmar</button>
          </div>
        </form>
      </div>
    </div>
  );
}
