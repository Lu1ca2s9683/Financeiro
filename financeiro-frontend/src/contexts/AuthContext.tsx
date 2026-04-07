'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { api, User, Grupo, Loja } from '@/services/api';
import { useRouter } from 'next/navigation';

interface AuthContextType {
  user: User | null;
  grupos: Grupo[];
  activeLoja: Loja | null;
  token: string | null;
  login: (token: string) => void;
  logout: () => void;
  switchStore: (lojaId: number) => Promise<void>;
  loading: boolean;
  canEdit: boolean; // Computed permission
}

const AuthContext = createContext<AuthContextType>({} as AuthContextType);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [grupos, setGrupos] = useState<Grupo[]>([]);
  const [activeLoja, setActiveLoja] = useState<Loja | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  // Load user data on mount if token exists
  useEffect(() => {
    const storedToken = localStorage.getItem('financeiro_token');
    if (storedToken) {
      setToken(storedToken);
      fetchMe();
    } else {
      setLoading(false);
    }
  }, []);

  const fetchMe = async () => {
    try {
      const data = await api.getMe();
      setUser(data.user);
      setGrupos(data.grupos);
      setActiveLoja(data.active_loja);
    } catch (error) {
      console.error("Erro ao carregar sessão:", error);
      logout();
    } finally {
      setLoading(false);
    }
  };

  const login = (newToken: string) => {
    localStorage.setItem('financeiro_token', newToken);
    setToken(newToken);
    fetchMe(); // Carrega dados
    router.push('/');
  };

  const logout = () => {
    localStorage.removeItem('financeiro_token');
    setUser(null);
    setGrupos([]);
    setActiveLoja(null);
    setToken(null);
    router.push('/login');
  };

  const switchStore = async (lojaId: number) => {
    try {
      const response = await api.switchStore(lojaId);
      setActiveLoja(response.active_loja);

      // Se a API retornou novo token (ver api.ts), atualizamos estado local também se necessário
      // Mas o api.ts já atualiza localStorage.
      // Precisamos forçar atualização do token no state se mudou?
      // api.switchStore já lidou com localStorage.
      // O ideal é recarregar dados ou apenas atualizar activeLoja.
      // Vamos recarregar 'me' para garantir consistência.
      await fetchMe();
      window.location.reload(); // Força reload para limpar estados de outras páginas (ex: FinanceiroContext)
    } catch (error) {
      alert('Erro ao trocar loja');
    }
  };

  const canEdit = activeLoja?.role !== 'LEITURA';

  return (
    <AuthContext.Provider value={{ user, grupos, activeLoja, token, login, logout, switchStore, loading, canEdit }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
