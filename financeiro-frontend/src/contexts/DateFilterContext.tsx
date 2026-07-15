'use client';
import React, { createContext, useContext, useState, ReactNode } from 'react';

interface DateFilterContextData {
    mes: number;
    ano: number;
    setMes: (mes: number) => void;
    setAno: (ano: number) => void;
}

const DateFilterContext = createContext<DateFilterContextData>({} as DateFilterContextData);

export function DateFilterProvider({ children }: { children: ReactNode }) {
    const dataAtual = new Date();
    const [mes, setMes] = useState(dataAtual.getMonth() + 1);
    const [ano, setAno] = useState(dataAtual.getFullYear());

    return (
        <DateFilterContext.Provider value={{ mes, ano, setMes, setAno }}>
            {children}
        </DateFilterContext.Provider>
    );
}

export const useDateFilter = () => useContext(DateFilterContext);
