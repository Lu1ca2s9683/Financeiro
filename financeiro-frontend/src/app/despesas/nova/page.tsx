'use client';

import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { DespesaForm } from '@/components/DespesaForm';

export default function NovaDespesaPage() {
  const router = useRouter();

  const handleSuccess = () => {
    alert('Despesa salva com sucesso!');
    router.push('/despesas');
  };

  return (
    <main className="p-8 max-w-3xl mx-auto">
      <Link href="/despesas" className="flex items-center gap-2 text-slate-500 hover:text-slate-800 mb-6 text-sm font-medium">
        <ArrowLeft size={16} /> Voltar para listagem
      </Link>

      <div className="bg-white border border-slate-200 rounded-xl p-8 shadow-sm">
        <h1 className="text-xl font-bold text-slate-900 mb-6">Nova Despesa</h1>
        <DespesaForm onSuccess={handleSuccess} />
      </div>
    </main>
  );
}
