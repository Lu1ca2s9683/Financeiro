from ninja import Router, Schema, Field
from ninja.errors import HttpError
from typing import List, Optional
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.db import transaction
from datetime import date

# Importações dos modelos e serviços
from ..models.entidades import (
    ContaPagar, 
    CategoriaDespesa, 
    FechamentoMensal,
    TaxaMaquininha, 
    PerfilTaxaCartao,
    Fornecedor
)
from ...infrastructure.vendas_client import VendasClientSQL, VendasAPIClientMock
from ...domain.services import ProcessadorFechamento, FaturamentoItemDTO

# Instância do Router
router = Router()

# ==============================================================================
# 1. ADAPTERS E REPOSITÓRIOS INTERNOS
# ==============================================================================

class DjangoRepositorioTaxas:
    """Busca as taxas configuradas no banco para o cálculo."""
    def buscar_taxa(self, loja_id: int, tipo: str, bandeira: str, parcelas: int):
        # 1. Tenta taxa específica
        taxa = TaxaMaquininha.objects.filter(
            perfil__loja_id_externo=loja_id,
            perfil__ativo=True,
            tipo=tipo,
            bandeira=bandeira
        ).first()
        
        # 2. Se não achar, tenta fallback para bandeira 'GERAL'
        if not taxa:
            taxa = TaxaMaquininha.objects.filter(
                perfil__loja_id_externo=loja_id,
                perfil__ativo=True,
                tipo=tipo,
                bandeira='GERAL'
            ).first()
            
        if taxa:
            return type('TaxaDTO', (), {'percentual': taxa.taxa_percentual, 'valor_fixo': taxa.taxa_fixa})
        return None

class DjangoRepositorioDespesas:
    """Soma despesas para o fechamento."""
    def somar_despesas_competencia(self, loja_id, mes, ano):
        from django.db.models import Sum
        val = ContaPagar.objects.filter(
            loja_id_externo=loja_id, 
            data_competencia__month=mes, 
            data_competencia__year=ano
        ).exclude(status='CANCELADO').aggregate(Sum('valor_liquido'))['valor_liquido__sum']
        return val or Decimal('0.00')

# ==============================================================================
# 2. SCHEMAS (DATA TRANSFER OBJECTS)
# ==============================================================================

# --- Schemas de Categoria ---
class CategoriaIn(Schema):
    nome: str
    ativa: bool = True

class CategoriaOut(Schema):
    id: int
    nome: str
    ativa: bool

# --- Schemas de Taxas ---
class TaxaItemOut(Schema):
    tipo: str
    bandeira: str
    taxa_percentual: Decimal
    dias_para_recebimento: int

class PerfilTaxaOut(Schema):
    id: int
    nome: str
    loja_id_externo: int
    data_inicio_vigencia: date
    ativo: bool
    taxas: List[TaxaItemOut] = []

    @staticmethod
    def resolve_taxas(obj):
        return list(obj.taxas.all())

# --- Schemas de Despesa ---
class DespesaIn(Schema):
    descricao: str
    loja_id: int
    categoria_id: int
    valor: Decimal
    data_competencia: date
    data_vencimento: date
    fornecedor_id: Optional[int] = None

class DespesaOut(Schema):
    id: int
    descricao: str
    valor_liquido: Decimal
    status: str
    data_competencia: date
    categoria: CategoriaOut = None 

class DespesaDetailOut(DespesaOut):
    valor_bruto: Decimal
    valor_desconto: Decimal
    valor_acrescimo: Decimal
    data_vencimento: date
    fornecedor_id: Optional[int] = None
    loja_id_externo: int

class StatusUpdate(Schema):
    status: str

# --- Schemas de Fechamento ---
class FechamentoOut(Schema):
    loja_id: int = Field(..., alias="loja_id_externo") 
    mes: int
    ano: int
    faturamento_bruto: Decimal
    total_taxas: Decimal
    receita_liquida: Decimal
    total_despesas: Decimal
    resultado_operacional: Decimal
    status: str

    class Config:
        from_attributes = True 

# ==============================================================================
# 3. ENDPOINTS
# ==============================================================================

# --- CATEGORIAS (CRUD) ---

@router.get("/categorias/", response=List[CategoriaOut])
def listar_categorias(request):
    """Lista todas as categorias de despesa ativas."""
    return CategoriaDespesa.objects.filter(ativa=True)

@router.post("/categorias/", response=CategoriaOut)
def criar_categoria(request, payload: CategoriaIn):
    """Cria uma nova categoria."""
    return CategoriaDespesa.objects.create(**payload.dict())

@router.put("/categorias/{categoria_id}", response=CategoriaOut)
def editar_categoria(request, categoria_id: int, payload: CategoriaIn):
    """Edita nome ou status da categoria."""
    cat = get_object_or_404(CategoriaDespesa, id=categoria_id)
    cat.nome = payload.nome
    cat.ativa = payload.ativa
    cat.save()
    return cat

@router.delete("/categorias/{categoria_id}")
def excluir_categoria(request, categoria_id: int):
    """Exclui categoria se não houver despesas vinculadas."""
    cat = get_object_or_404(CategoriaDespesa, id=categoria_id)
    if ContaPagar.objects.filter(categoria=cat).exists():
        raise HttpError(400, "Não é possível excluir categoria com despesas vinculadas.")
    cat.delete()
    return {"success": True}

# --- TAXAS DE CARTÃO ---

@router.get("/taxas/perfis/", response=List[PerfilTaxaOut])
def listar_perfis_taxas(request, loja_id: Optional[int] = None):
    """Lista perfis de taxas, opcionalmente filtrando por loja."""
    qs = PerfilTaxaCartao.objects.filter(ativo=True).prefetch_related('taxas')
    if loja_id:
        qs = qs.filter(loja_id_externo=loja_id)
    return qs

# --- DESPESAS (CRUD) ---

@router.get("/despesas/", response=List[DespesaOut])
def listar_despesas(
    request, 
    loja_id: Optional[int] = None,
    mes: Optional[int] = None, # <--- PARÂMETROS ADICIONADOS
    ano: Optional[int] = None  # <--- PARA O FILTRO
):
    """Lista despesas, opcionalmente filtrando por loja e competência."""
    qs = ContaPagar.objects.all().select_related('categoria')
    
    if loja_id:
        qs = qs.filter(loja_id_externo=loja_id)
    
    # Lógica de Filtro por Data (CORREÇÃO)
    if mes and ano:
        qs = qs.filter(data_competencia__month=mes, data_competencia__year=ano)
        
    return qs

@router.get("/despesas/{despesa_id}", response=DespesaDetailOut)
def obter_despesa(request, despesa_id: int):
    """Retorna detalhes de uma despesa."""
    return get_object_or_404(ContaPagar, id=despesa_id)

@router.patch("/despesas/{despesa_id}/status", response=DespesaOut)
def atualizar_status_despesa(request, despesa_id: int, payload: StatusUpdate):
    """Atualiza o status da despesa, validando fechamento."""
    despesa = get_object_or_404(ContaPagar, id=despesa_id)

    # Validar fechamento
    fechamento = FechamentoMensal.objects.filter(
        loja_id_externo=despesa.loja_id_externo,
        mes=despesa.data_competencia.month,
        ano=despesa.data_competencia.year
    ).first()

    if fechamento and fechamento.status == 'CONCLUIDO':
        raise HttpError(400, f"Não é possível alterar despesa em mês fechado ({despesa.data_competencia.strftime('%m/%Y')}).")

    # Validar se o status existe nas opções do model
    opcoes_status = dict(ContaPagar.STATUS_CHOICES).keys()
    if payload.status not in opcoes_status:
        raise HttpError(400, f"Status inválido. Opções: {list(opcoes_status)}")

    despesa.status = payload.status
    despesa.save()
    return despesa

@router.post("/despesas/", response=DespesaOut)
def criar_despesa(request, payload: DespesaIn):
    """Cria uma nova conta a pagar."""
    if not CategoriaDespesa.objects.filter(id=payload.categoria_id).exists():
        raise HttpError(404, f"Categoria de Despesa com ID {payload.categoria_id} não encontrada.")
    
    categoria = CategoriaDespesa.objects.get(id=payload.categoria_id)
    
    fornecedor = None
    if payload.fornecedor_id:
        if not Fornecedor.objects.filter(id=payload.fornecedor_id).exists():
            raise HttpError(404, f"Fornecedor com ID {payload.fornecedor_id} não encontrado.")
        fornecedor = Fornecedor.objects.get(id=payload.fornecedor_id)

    despesa = ContaPagar.objects.create(
        descricao=payload.descricao,
        loja_id_externo=payload.loja_id,
        categoria=categoria,
        fornecedor=fornecedor,
        valor_bruto=payload.valor,
        data_competencia=payload.data_competencia,
        data_vencimento=payload.data_vencimento,
        criado_por=request.user if request.user.is_authenticated else None
    )
    return despesa

@router.put("/despesas/{despesa_id}", response=DespesaOut)
def editar_despesa(request, despesa_id: int, payload: DespesaIn):
    """Atualiza uma despesa e recalcula valores."""
    despesa = get_object_or_404(ContaPagar, id=despesa_id)

    # Validar fechamento (Data Atual)
    fechamento_atual = FechamentoMensal.objects.filter(
        loja_id_externo=despesa.loja_id_externo,
        mes=despesa.data_competencia.month,
        ano=despesa.data_competencia.year
    ).first()

    if fechamento_atual and fechamento_atual.status == 'CONCLUIDO':
        raise HttpError(400, f"Não é possível editar despesa de mês fechado ({despesa.data_competencia.strftime('%m/%Y')}).")

    # Validar fechamento (Nova Data - se mudou)
    if payload.data_competencia != despesa.data_competencia:
        fechamento_novo = FechamentoMensal.objects.filter(
            loja_id_externo=payload.loja_id,
            mes=payload.data_competencia.month,
            ano=payload.data_competencia.year
        ).first()
        if fechamento_novo and fechamento_novo.status == 'CONCLUIDO':
            raise HttpError(400, f"Não é possível mover despesa para mês fechado ({payload.data_competencia.strftime('%m/%Y')}).")

    if not CategoriaDespesa.objects.filter(id=payload.categoria_id).exists():
        raise HttpError(404, f"Categoria {payload.categoria_id} não encontrada.")
    categoria = CategoriaDespesa.objects.get(id=payload.categoria_id)

    fornecedor = None
    if payload.fornecedor_id:
        fornecedor = get_object_or_404(Fornecedor, id=payload.fornecedor_id)

    despesa.descricao = payload.descricao
    despesa.loja_id_externo = payload.loja_id
    despesa.categoria = categoria
    despesa.fornecedor = fornecedor
    despesa.valor_bruto = payload.valor
    despesa.data_competencia = payload.data_competencia
    despesa.data_vencimento = payload.data_vencimento
    despesa.save()
    
    return despesa

@router.delete("/despesas/{despesa_id}")
def excluir_despesa(request, despesa_id: int):
    """Exclui uma despesa."""
    despesa = get_object_or_404(ContaPagar, id=despesa_id)
    despesa.delete()
    return {"success": True, "message": f"Despesa {despesa_id} excluída."}

# --- FECHAMENTO ---

@router.post("/fechamento/calcular/{loja_id}/{mes}/{ano}", response=FechamentoOut)
def calcular_fechamento(request, loja_id: int, mes: int, ano: int):
    """Calcula e persiste o fechamento mensal."""
    # 1. Instancia dependências (SQL Real ou Mock)
    try:
        vendas_client = VendasClientSQL() 
    except Exception as e:
        print(f"Erro conexão SQL: {e}")
        vendas_client = VendasAPIClientMock()

    repo_taxas = DjangoRepositorioTaxas()
    repo_despesas = DjangoRepositorioDespesas()

    # 2. Executa Domínio (Cálculos)
    processador = ProcessadorFechamento(repo_taxas, repo_despesas)
    dados_vendas = vendas_client.get_faturamento_por_loja(loja_id, mes, ano)
    resultado = processador.executar_fechamento(loja_id, mes, ano, dados_vendas)

    # 3. Persiste Resultado
    with transaction.atomic():
        fechamento, created = FechamentoMensal.objects.update_or_create(
            loja_id_externo=loja_id,
            mes=mes,
            ano=ano,
            defaults={
                'faturamento_bruto': resultado.faturamento_bruto,
                'total_taxas': resultado.total_taxas,
                'receita_liquida': resultado.receita_liquida,
                'total_despesas': resultado.despesas_totais,
                'resultado_operacional': resultado.resultado_final,
                'status': 'ABERTO',
                'dados_auditoria_snapshot': resultado.snapshot_dados
            }
        )
    
    return fechamento