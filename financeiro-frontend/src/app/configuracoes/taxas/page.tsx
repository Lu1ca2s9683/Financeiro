'use client';

import { useEffect, useState } from 'react';
import { api, PerfilTaxa } from '@/services/api';
import Link from 'next/link';
import { ArrowLeft, CreditCard, Calendar, Building2 } from 'lucide-react';

export default function TaxasPage() {
  const [perfis, setPerfis] = useState<PerfilTaxa[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Carrega perfis (filtro de loja opcional, aqui carregamos todos para visão geral)
    api.getPerfisTaxas()
      .then(setPerfis)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="p-8 space-y-8 animate-enter max-w-6xl mx-auto">
      <div className="flex items-center gap-4">
        <Link href="/configuracoes" className="p-2 hover:bg-slate-100 rounded-lg transition-colors">
          <ArrowLeft size={20} className="text-slate-500" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Taxas de Cartão</h1>
          <p className="text-slate-500">Perfis de taxas negociados com adquirentes (Stone, Cielo, etc)</p>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-500">Carregando perfis...</div>
      ) : (
        <div className="grid grid-cols-1 gap-6">
          {perfis.map((perfil) => (
            <div key={perfil.id} className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition-shadow">
              {/* Header do Perfil */}
              <div className="bg-slate-50 px-6 py-4 border-b border-slate-200 flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <div className="bg-indigo-100 p-2 rounded-lg text-indigo-600">
                    <CreditCard size={20} />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-800">{perfil.nome}</h3>
                    <div className="flex items-center gap-4 text-xs text-slate-500 mt-1">
                      <span className="flex items-center gap-1"><Building2 size={12}/> Loja ID: {perfil.loja_id_externo}</span>
                      <span className="flex items-center gap-1"><Calendar size={12}/> Vigência: {perfil.data_inicio_vigencia}</span>
                    </div>
                  </div>
                </div>
                <div>
                  {perfil.ativo ? (
                    <span className="px-3 py-1 bg-emerald-100 text-emerald-800 rounded-full text-xs font-bold uppercase tracking-wide">Ativo</span>
                  ) : (
                    <span className="px-3 py-1 bg-slate-100 text-slate-600 rounded-full text-xs font-bold uppercase tracking-wide">Inativo</span>
                  )}
                </div>
              </div>

              {/* Tabela de Taxas do Perfil */}
              <div className="p-0">
                <table className="w-full text-sm text-left">
                  <thead className="bg-white text-slate-500 font-medium border-b border-slate-100">
                    <tr>
                      <th className="px-6 py-3 font-normal">Modalidade</th>
                      <th className="px-6 py-3 font-normal">Bandeira</th>
                      <th className="px-6 py-3 font-normal">Dias Receb.</th>
                      <th className="px-6 py-3 font-normal text-right">Taxa (%)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {perfil.taxas.map((taxa, idx) => (
                      <tr key={idx} className="hover:bg-slate-50/50">
                        <td className="px-6 py-3 font-medium text-slate-700">{taxa.tipo}</td>
                        <td className="px-6 py-3 text-slate-500">{taxa.bandeira}</td>
                        <td className="px-6 py-3 text-slate-500">D+{taxa.dias_para_recebimento}</td>
                        <td className="px-6 py-3 text-right font-mono font-bold text-indigo-600">
                          {Number(taxa.taxa_percentual).toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                    {perfil.taxas.length === 0 && (
                        <tr><td colSpan={4} className="px-6 py-4 text-center text-slate-400 italic">Nenhuma taxa configurada neste perfil.</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          ))}

          {perfis.length === 0 && (
            <div className="text-center py-12 bg-slate-50 rounded-xl border border-dashed border-slate-300">
              <p className="text-slate-500">Nenhum perfil de taxa encontrado.</p>
              <p className="text-sm text-slate-400 mt-2">Cadastre um perfil através do Django Admin.</p>
            </div>
          )}
        </div>
      )}
    </main>
  );
}