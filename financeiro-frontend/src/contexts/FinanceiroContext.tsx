'use client';

import React, { createContext, useContext, useState, ReactNode, useEffect } from 'react';

interface FinanceiroContextProps {
  lojaId: number;
  setLojaId: (id: number) => void;
  mes: number;
  setMes: (m: number) => void;
  ano: number;
  setAno: (a: number) => void;
  periodoFormatado: string;
  dataCompetenciaISO: string;
  atualizarPeriodoPorInput: (isoValue: string) => void;
}

const FinanceiroContext = createContext<FinanceiroContextProps | undefined>(undefined);

export function FinanceiroProvider({ children }: { children: ReactNode }) {
  // Inicializa com a data atual (ou Dezembro/2025 para testes, se preferir)
  const dataAtual = new Date();
  const [lojaId, setLojaId] = useState(1);
  const [mes, setMes] = useState(dataAtual.getMonth() + 1); // 1-12
  const [ano, setAno] = useState(dataAtual.getFullYear());

  // Formatação visual (Ex: "Janeiro / 2026")
  // Importante: mes - 1 porque o Date do JS usa meses 0-11
  const periodoFormatado = new Date(ano, mes - 1, 1).toLocaleDateString('pt-BR', {
    month: 'long',
    year: 'numeric',
  });

  // Formatação ISO para inputs type="month" (Ex: "2026-01")
  const dataCompetenciaISO = `${ano}-${String(mes).padStart(2, '0')}`;

  // Helper para atualizar via input type="month"
  const atualizarPeriodoPorInput = (isoValue: string) => {
    if (!isoValue) return;
    const [y, m] = isoValue.split('-').map(Number);
    setAno(y);
    setMes(m);
  };

  return (
    <FinanceiroContext.Provider value={{
      lojaId, setLojaId,
      mes, setMes,
      ano, setAno,
      periodoFormatado,
      dataCompetenciaISO,
      atualizarPeriodoPorInput
    }}>
      {children}
    </FinanceiroContext.Provider>
  );
}

export function useFinanceiro() {
  const context = useContext(FinanceiroContext);
  if (!context) {
    throw new Error('useFinanceiro deve ser usado dentro de um FinanceiroProvider');
  }
  return context;
}