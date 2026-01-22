'use client';

import { useState, useEffect } from 'react';

export function DebugPanel() {
  const [status, setStatus] = useState<'checking' | 'ok' | 'error'>('checking');
  const [msg, setMsg] = useState('');
  const [envUrl, setEnvUrl] = useState('');

  useEffect(() => {
    // 1. Verifica qual URL está sendo usada
    const url = process.env.NEXT_PUBLIC_API_URL;
    setEnvUrl(url || 'NÃO DEFINIDA');

    if (!url) {
      setStatus('error');
      setMsg('Variável NEXT_PUBLIC_API_URL não encontrada!');
      return;
    }

    // 2. Tenta um ping simples na API (endpoint de categorias é leve)
    fetch(`${url}/categorias/`)
      .then(res => {
        if (res.ok) {
          setStatus('ok');
          setMsg(`Conectado com sucesso! Status: ${res.status}`);
        } else {
          setStatus('error');
          setMsg(`Erro na resposta: ${res.status} ${res.statusText}`);
        }
      })
      .catch(err => {
        setStatus('error');
        setMsg(`Erro de Rede/CORS: ${err.message}`);
      });
  }, []);

  if (process.env.NODE_ENV === 'production' && status === 'ok') return null; // Esconde em prod se tiver ok

  return (
    <div className="fixed bottom-4 right-4 p-4 bg-slate-800 text-white rounded-lg shadow-2xl z-50 text-xs font-mono max-w-sm border border-slate-600">
      <h3 className="font-bold text-yellow-400 mb-2">🕵️ DEBUGGER FINANCEIRO</h3>
      
      <div className="space-y-2">
        <div>
          <span className="text-slate-400">API URL:</span>
          <p className="bg-slate-900 p-1 rounded break-all">{envUrl}</p>
        </div>

        <div>
          <span className="text-slate-400">Status:</span>
          <div className={`mt-1 p-2 rounded font-bold ${
            status === 'ok' ? 'bg-green-900 text-green-300' : 
            status === 'error' ? 'bg-red-900 text-red-300' : 'bg-blue-900 text-blue-300'
          }`}>
            {status === 'checking' ? 'Testando conexão...' : status === 'ok' ? 'ONLINE' : 'FALHA'}
          </div>
        </div>

        {msg && (
          <div className="border-t border-slate-600 pt-2 text-slate-300">
            {msg}
          </div>
        )}
        
        <div className="text-[10px] text-slate-500 pt-2 text-center">
          Se der "Erro de Rede", verifique CORS no Backend.
        </div>
      </div>
    </div>
  );
}