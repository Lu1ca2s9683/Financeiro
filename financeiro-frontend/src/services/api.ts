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

export const api = {
  // --- Categorias ---
  getCategorias: async (): Promise<Categoria[]> => {
    const res = await fetch(`${API_BASE_URL}/categorias/`);
    if (!res.ok) throw new Error('Falha ao buscar categorias');
    return res.json();
  },

  createCategoria: async (nome: string) => {
    const res = await fetch(`${API_BASE_URL}/categorias/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome, ativa: true })
    });
    if (!res.ok) throw new Error('Erro ao criar categoria');
    return res.json();
  },

  updateCategoria: async (id: number, nome: string) => {
    const res = await fetch(`${API_BASE_URL}/categorias/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nome, ativa: true })
    });
    if (!res.ok) throw new Error('Erro ao atualizar categoria');
    return res.json();
  },

  deleteCategoria: async (id: number) => {
    const res = await fetch(`${API_BASE_URL}/categorias/${id}`, { method: 'DELETE' });
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
    const res = await fetch(url);
    if (!res.ok) throw new Error('Falha ao buscar perfis de taxas');
    return res.json();
  },

  // --- Despesas e Fechamento ---
  getFechamento: async (lojaId: number, mes: number, ano: number): Promise<Fechamento> => {
    const res = await fetch(`${API_BASE_URL}/fechamento/calcular/${lojaId}/${mes}/${ano}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
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
    
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error('Falha ao buscar despesas');
    return res.json();
  },

  createDespesa: async (data: any) => {
    const res = await fetch(`${API_BASE_URL}/despesas/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Erro ao salvar despesa');
    }
    return res.json();
  },

  deleteDespesa: async (id: number) => {
    const res = await fetch(`${API_BASE_URL}/despesas/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Falha ao excluir');
    return res.json();
  }
};