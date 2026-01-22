// src/services/api.ts

// Define a URL base. Prioriza a variável de ambiente.
// Se não houver variável (ex: desenvolvimento local sem .env), usa localhost.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/financeiro';

console.log('🔗 API_BASE_URL configurada:', API_BASE_URL); // Debug no console do navegador

export interface Categoria {
  id: number;
  nome: string;
  ativa: boolean;
}

export interface TaxaItem {
  tipo: string;
  bandeira: string;
  taxa_percentual: number;
  dias_para_recebimento: number;
}

export interface PerfilTaxa {
  id: number;
  nome: string;
  loja_id_externo: number;
  data_inicio_vigencia: string;
  ativo: boolean;
  taxas: TaxaItem[];
}

export interface Despesa {
  id: number;
  descricao: string;
  valor_liquido: number;
  status: string;
  data_competencia: string;
  categoria?: { id: number; nome: string };
  dias_para_vencimento?: number;
  is_vencendo?: boolean;
  is_atrasado?: boolean;
}

export interface DashboardResumo {
  percentual_pago: number;
  percentual_atrasado: number;
  percentual_previsto: number;
  total_despesas_mes: number;
  despesas_vencendo_semana: number;
  despesas_atrasadas: number;
  saude_financeira: 'SAUDAVEL' | 'ATENCAO' | 'CRITICO';
  mensagem_assistente: string;
}

export interface DespesaDetail extends Despesa {
  valor_bruto: number;
  valor_desconto: number;
  valor_acrescimo: number;
  data_vencimento: string;
  fornecedor_id?: number;
  loja_id_externo: number;
}

export interface Fechamento {
  loja_id: number;
  mes: number;
  ano: number;
  faturamento_bruto: number;
  total_taxas: number;
  receita_liquida: number;
  total_despesas: number;
  resultado_operacional: number;
  status: string;
}

// --- Types ---
export interface AuthResponse {
  token: string;
}

export interface User {
  id: number;
  nome: string;
  email: string;
}

export interface Loja {
  id: number;
  nome: string;
  role: string;
}

export interface Grupo {
  id: number;
  nome: string;
  role: string;
  lojas: Loja[];
}

export interface MeResponse {
  user: User;
  grupos: Grupo[];
  active_loja: Loja | null;
}

// --- Helpers ---
const getHeaders = () => {
  const token = localStorage.getItem('financeiro_token');
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {})
  };
};

export const api = {
  // --- Auth ---
  login: async (username: string, password: string): Promise<AuthResponse> => {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    if (!res.ok) throw new Error('Falha no login');
    return res.json();
  },

  getMe: async (): Promise<MeResponse> => {
    const res = await fetch(`${API_BASE_URL}/auth/me`, {
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Falha ao buscar dados do usuário');
    return res.json();
  },

  switchStore: async (loja_id: number): Promise<{ active_loja: Loja }> => {
    const res = await fetch(`${API_BASE_URL}/auth/switch-loja`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ loja_id })
    });

    // Hack: Pega o novo token se vier no header (pelo mock)
    const newToken = res.headers.get("X-New-Token");
    if (newToken) {
        localStorage.setItem("financeiro_token", newToken);
    }

    if (!res.ok) throw new Error('Falha ao trocar de loja');
    return res.json();
  },

  // --- Categorias ---
  getCategorias: async (): Promise<Categoria[]> => {
    const res = await fetch(`${API_BASE_URL}/categorias/`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Falha ao buscar categorias');
    return res.json();
  },

  createCategoria: async (nome: string) => {
    const res = await fetch(`${API_BASE_URL}/categorias/`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ nome, ativa: true })
    });
    if (!res.ok) throw new Error('Erro ao criar categoria');
    return res.json();
  },

  updateCategoria: async (id: number, nome: string) => {
    const res = await fetch(`${API_BASE_URL}/categorias/${id}`, {
      method: 'PUT',
      headers: getHeaders(),
      body: JSON.stringify({ nome, ativa: true })
    });
    if (!res.ok) throw new Error('Erro ao atualizar categoria');
    return res.json();
  },

  deleteCategoria: async (id: number) => {
    const res = await fetch(`${API_BASE_URL}/categorias/${id}`, { method: 'DELETE', headers: getHeaders() });
    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Erro ao excluir categoria');
    }
    return res.json();
  },

  // --- Taxas ---
  getPerfisTaxas: async (lojaId?: number): Promise<PerfilTaxa[]> => {
    const url = lojaId 
      ? `${API_BASE_URL}/taxas/perfis/?loja_id=${lojaId}` 
      : `${API_BASE_URL}/taxas/perfis/`;
    const res = await fetch(url, { headers: getHeaders() });
    if (!res.ok) throw new Error('Falha ao buscar perfis de taxas');
    return res.json();
  },

  // --- Despesas e Fechamento ---
  getDashboardResumo: async (lojaId: number, mes: number, ano: number): Promise<DashboardResumo> => {
    const res = await fetch(`${API_BASE_URL}/dashboard/resumo/${lojaId}/${mes}/${ano}`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Falha ao buscar resumo do dashboard');
    return res.json();
  },

  getFechamento: async (lojaId: number, mes: number, ano: number): Promise<Fechamento> => {
    const res = await fetch(`${API_BASE_URL}/fechamento/calcular/${lojaId}/${mes}/${ano}`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({}) 
    });
    if (!res.ok) throw new Error('Falha ao buscar fechamento');
    return res.json();
  },

  // Método que aplica o filtro
  getDespesas: async (lojaId: number, mes?: number, ano?: number): Promise<Despesa[]> => {
    let url = `${API_BASE_URL}/despesas/?loja_id=${lojaId}`;
    
    // Adiciona os filtros na URL se os parâmetros existirem
    if (mes && ano) {
      url += `&mes=${mes}&ano=${ano}`;
    }
    
    console.log("📡 Buscando despesas na URL:", url);
    
    const res = await fetch(url, { cache: 'no-store', headers: getHeaders() });
    if (!res.ok) throw new Error('Falha ao buscar despesas');
    return res.json();
  },

  getDespesa: async (id: number): Promise<DespesaDetail> => {
    const res = await fetch(`${API_BASE_URL}/despesas/${id}`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Falha ao buscar detalhes da despesa');
    return res.json();
  },

  createDespesa: async (data: any) => {
    const res = await fetch(`${API_BASE_URL}/despesas/`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data),
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Erro ao salvar despesa');
    }
    return res.json();
  },

  updateDespesa: async (id: number, data: any): Promise<Despesa> => {
    const res = await fetch(`${API_BASE_URL}/despesas/${id}`, {
      method: 'PUT',
      headers: getHeaders(),
      body: JSON.stringify(data),
    });
    if (!res.ok) {
         const errorData = await res.json().catch(() => ({}));
         throw new Error(errorData.detail || 'Erro ao atualizar despesa');
    }
    return res.json();
  },

  updateDespesaStatus: async (id: number, status: string): Promise<Despesa> => {
    const res = await fetch(`${API_BASE_URL}/despesas/${id}/status`, {
      method: 'PATCH',
      headers: getHeaders(),
      body: JSON.stringify({ status }),
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Erro ao atualizar status');
    }
    return res.json();
  },

  deleteDespesa: async (id: number) => {
    const res = await fetch(`${API_BASE_URL}/despesas/${id}`, { method: 'DELETE', headers: getHeaders() });
    if (!res.ok) throw new Error('Falha ao excluir');
    return res.json();
  }
};