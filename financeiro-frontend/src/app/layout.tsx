import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Sidebar } from '@/components/Sidebar';
import { FinanceiroProvider } from '@/contexts/FinanceiroContext';
import { AuthProvider } from '@/contexts/AuthContext';
import { DebugPanel } from '@/components/DebugPanel';
import { MainLayout } from '@/components/MainLayout';

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
        <AuthProvider>
          <FinanceiroProvider>
             <MainLayout>{children}</MainLayout>
             <DebugPanel />
          </FinanceiroProvider>
        </AuthProvider>
      </body>
    </html>
  );
}