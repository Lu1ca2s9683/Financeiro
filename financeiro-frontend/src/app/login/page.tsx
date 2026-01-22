'use client';

import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { Lock, User, ArrowRight, Wallet } from 'lucide-react';

export default function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Importamos api aqui apenas para chamar o login antes de passar pro contexto
  const { api } = require('@/services/api');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await api.login(username, password);
      login(response.token);
    } catch (err: any) {
      console.error(err);
      if (err.message === 'FORBIDDEN_DEVICE') {
        setError('Acesso não autorizado neste dispositivo. Este dispositivo ainda não foi liberado pelo administrador global. Após a liberação, tente novamente.');
      } else {
        setError('Credenciais inválidas ou erro no servidor.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl overflow-hidden border border-slate-100">

        {/* Header */}
        <div className="bg-indigo-600 p-8 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-white/10 rounded-2xl backdrop-blur-sm mb-4">
            <Wallet className="text-white" size={32} />
          </div>
          <h1 className="text-2xl font-bold text-white">Sistema Financeiro</h1>
          <p className="text-indigo-200 text-sm mt-2">Acesse sua conta para continuar</p>
        </div>

        {/* Form */}
        <div className="p-8">
          <form onSubmit={handleSubmit} className="space-y-6">

            {error && (
              <div className="p-3 bg-rose-50 text-rose-600 text-sm rounded-lg border border-rose-100 text-center">
                {error}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5 ml-1">Usuário</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                    <User size={18} />
                  </div>
                  <input
                    required
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-slate-900"
                    placeholder="Seu usuário"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5 ml-1">Senha</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                    <Lock size={18} />
                  </div>
                  <input
                    required
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 transition-all text-slate-900"
                    placeholder="••••••••"
                  />
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold py-3 rounded-xl transition-all flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed shadow-lg shadow-indigo-200"
            >
              {loading ? (
                'Entrando...'
              ) : (
                <>
                  Entrar no Sistema <ArrowRight size={18} />
                </>
              )}
            </button>
          </form>

          <div className="mt-8 text-center">
            <p className="text-xs text-slate-400">
              Acesso restrito a gestores autorizados.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
