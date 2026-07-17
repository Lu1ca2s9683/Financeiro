/* eslint-disable @typescript-eslint/no-explicit-any, @typescript-eslint/no-unused-vars, react-hooks/exhaustive-deps, react-hooks/set-state-in-effect, @typescript-eslint/no-require-imports */
// src/services/api.ts

// Define a URL base. Prioriza a variável de ambiente.
// Se não houver variável (ex: desenvolvimento local sem .env), usa localhost.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api/financeiro';

console.log('🔗 API_BASE_URL configurada:', API_BASE_URL); // Debug no console do navegador

export interface Categoria {
  id: number;
  nome: string;
  grupo_contabil: string;
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

export interface Rateio {
  id?: number;
  descricao: string;
  valor: number;
  categoria_id?: number;
}

export interface ExtratoItem {
  data_transacao: string;
  descricao_original: string;
  valor: number;
  tipo: string;
  categoria_sugerida_id?: number | null;
}

export interface Despesa {
  id: number;
  descricao: string;
  valor_liquido: number;
  data_competencia: string;
  categoria?: { id: number; nome: string };
  data_transacao?: string;
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
  splits?: Rateio[];
  fornecedor_id?: number;
  loja_id_externo: number;
}

export interface DRELancamento {
  despesa_id: number;
  rateio_id: number | null;
  tipo_origem: string;
  data_transacao: string;
  descricao: string;
  fornecedor_nome: string | null;
  valor: number;
}

export interface DRECategoria {
  categoria_id: number;
  categoria_nome: string;
  total: number;
  quantidade_lancamentos: number;
  lancamentos: DRELancamento[];
}

export interface DREGrupo {
  grupo_contabil: string;
  descricao: string;
  total: number;
  percentual_receita: number;
  categorias: DRECategoria[];
}

export interface DRELinha {
  codigo: string;
  descricao: string;
  tipo: string;
  nivel: number;
  valor: number;
  percentual_receita: number;
  ordem: number;
}

export interface DREData {
  identificacao: {
    loja_id: number;
    loja_nome: string;
    mes: number;
    ano: number;
    periodo_descricao: string;
    regime: string;
    gerado_em: string;
    gerado_por: string;
  };
  resumo: {
    receita_bruta: number;
    impostos: number;
    receita_liquida: number;
    custos_produtos: number;
    lucro_bruto: number;
    despesas_pessoal: number;
    despesas_administrativas: number;
    despesas_marketing: number;
    despesas_operacionais: number;
    resultado_operacional: number;
    taxas_cartao: number;
    outras_despesas_financeiras: number;
    despesas_financeiras_total: number;
    lucro_liquido: number;
    margem_bruta_percentual: number;
    margem_operacional_percentual: number;
    margem_liquida_percentual: number;
  };
  linhas: DRELinha[];
  grupos_detalhados: DREGrupo[];
  qualidade_dados: {
    quantidade_despesas_consideradas: number;
    quantidade_despesas_sem_rateio: number;
    quantidade_despesas_com_rateio_valido: number;
    quantidade_despesas_com_rateio_invalido: number;
    valor_despesas_com_rateio_invalido: number;
    valor_total_despesas_consideradas: number;
    possui_rateios_invalidos: boolean;
  };
}

export interface Fechamento {
  loja_id: number;
  mes: number;
  ano: number;
  faturamento_bruto: number;
  total_dinheiro: number;
  total_cartao: number;
  total_pix: number;
  impostos: number;
  receita_liquida: number;
  custos_produtos: number;
  lucro_bruto: number;
  despesas_operacionais: number;
  resultado_operacional: number;
  total_taxas: number;
  despesas_financeiras: number;
  lucro_liquido: number;
  status: string;
}

// --- Types ---
export interface AuthResponse {
  token: string;
}

export interface ContaBancaria {
  id: number;
  nome: string;
  tipo: string;
  banco_codigo: string;
  agencia: string;
  conta: string;
  saldo_inicial: number;
  saldo_atual: number;
  ativo: boolean;
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

    if (res.status === 403) {
      throw new Error('FORBIDDEN_DEVICE');
    }

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

    if (!res.ok) throw new Error('Falha ao trocar de loja');

    const data = await res.json();

    // Atualiza o token a partir do JSON response em vez do Header
    if (data.token) {
        localStorage.setItem("financeiro_token", data.token);
    }

    return data;
  },

  // --- Tesouraria (Contas e Transferências) ---
  getContasBancarias: async (): Promise<ContaBancaria[]> => {
    const res = await fetch(`${API_BASE_URL}/contas/`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Falha ao buscar contas bancárias');
    return res.json();
  },

  createContaBancaria: async (data: unknown): Promise<ContaBancaria> => {
    const res = await fetch(`${API_BASE_URL}/contas/`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Falha ao criar conta bancária');
    return res.json();
  },

  createTransferencia: async (data: unknown) => {
    const res = await fetch(`${API_BASE_URL}/contas/transferencia`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify(data)
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Erro ao realizar transferência');
    }
    return res.json();
  },

  // --- Categorias ---
  getCategorias: async (): Promise<Categoria[]> => {
    const res = await fetch(`${API_BASE_URL}/categorias/`, { headers: getHeaders() });
    if (!res.ok) throw new Error('Falha ao buscar categorias');
    return res.json();
  },

  createCategoria: async (nome: string, grupo_contabil: string = 'ADMINISTRATIVA') => {
    const res = await fetch(`${API_BASE_URL}/categorias/`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ nome, grupo_contabil, ativa: true })
    });
    if (!res.ok) throw new Error('Erro ao criar categoria');
    return res.json();
  },

  updateCategoria: async (id: number, nome: string, grupo_contabil: string = 'ADMINISTRATIVA') => {
    const res = await fetch(`${API_BASE_URL}/categorias/${id}`, {
      method: 'PUT',
      headers: getHeaders(),
      body: JSON.stringify({ nome, grupo_contabil, ativa: true })
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

  getDre: async (lojaId: number, mes: number, ano: number): Promise<DREData> => {
    const res = await fetch(`${API_BASE_URL}/dre/${lojaId}/${mes}/${ano}`, {
      method: 'GET',
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Falha ao carregar DRE');
    return res.json();
  },

  downloadDrePdf: async (lojaId: number, mes: number, ano: number): Promise<void> => {
    const res = await fetch(`${API_BASE_URL}/dre/${lojaId}/${mes}/${ano}/pdf`, {
      method: 'GET',
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Falha ao baixar PDF');

    let filename = `DRE_${lojaId}_${mes}_${ano}.pdf`;
    const disposition = res.headers.get('Content-Disposition');
    if (disposition && disposition.indexOf('filename=') !== -1) {
        const matches = /filename="([^"]+)"/.exec(disposition);
        if (matches != null && matches[1]) filename = matches[1];
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    try {
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    } finally {
        window.URL.revokeObjectURL(url);
    }
  },

  downloadDreXml: async (lojaId: number, mes: number, ano: number): Promise<void> => {
    const res = await fetch(`${API_BASE_URL}/dre/${lojaId}/${mes}/${ano}/xml`, {
      method: 'GET',
      headers: getHeaders()
    });
    if (!res.ok) throw new Error('Falha ao baixar XML');

    let filename = `DRE_${lojaId}_${mes}_${ano}.xml`;
    const disposition = res.headers.get('Content-Disposition');
    if (disposition && disposition.indexOf('filename=') !== -1) {
        const matches = /filename="([^"]+)"/.exec(disposition);
        if (matches != null && matches[1]) filename = matches[1];
    }

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    try {
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    } finally {
        window.URL.revokeObjectURL(url);
    }
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

  importExtrato: async (file: File): Promise<ExtratoItem[]> => {

    const formData = new FormData();
    formData.append('file', file);

    const headers = getHeaders();
    delete (headers as any)['Content-Type']; // Let browser set boundary

    const res = await fetch(`${API_BASE_URL}/import-statement/`, {
      method: 'POST',
      headers: headers,
      body: formData,
    });
    if (!res.ok) throw new Error('Falha ao importar extrato');
    return res.json();
  },

  createDespesa: async (data: unknown) => {
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

  updateDespesa: async (id: number, data: unknown): Promise<Despesa> => {
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

  deleteDespesa: async (id: number) => {
    const res = await fetch(`${API_BASE_URL}/despesas/${id}`, { method: 'DELETE', headers: getHeaders() });
    if (!res.ok) throw new Error('Falha ao excluir');
    return res.json();
  },
  importarExtratoDespesas: async (lojaId: number | string, file: File): Promise<ExtratoItem[]> => {
    const formData = new FormData();
    formData.append('file', file);
    const headers = getHeaders();
    delete (headers as any)['Content-Type']; // Remove para o browser colocar o boundary

    const res = await fetch(`${API_BASE_URL}/extrato/importar-despesas/${lojaId}/`, {
      method: 'POST',
      headers: headers,
      body: formData,
    });

    if (!res.ok) {
        throw new Error('Falha na importação do extrato');
    }
    return res.json();
  },
};