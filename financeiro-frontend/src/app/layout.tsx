import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Sidebar } from '@/components/Sidebar';
import { FinanceiroProvider } from '@/contexts/FinanceiroContext'; // <--- Import obrigatório
import { DebugPanel } from '@/components/DebugPanel';

const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Sistema Financeiro Corporativo',
  description: 'Gestão de Fechamento e Despesas',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR" className={inter.variable}>
      <body className="font-sans antialiased bg-slate-50 text-slate-900">
        {/* O Provider deve envolver a Sidebar e o conteúdo para compartilhar o estado */}
        <FinanceiroProvider>
          <div className="flex min-h-screen">
            <Sidebar />
            
            {/* Conteúdo Principal com margem para a Sidebar fixa */}
            <div className="flex-1 ml-72 transition-all duration-300 ease-in-out">
              {children}
            </div>
          </div>

          <DebugPanel />

        </FinanceiroProvider>
      </body>
    </html>
  );
}