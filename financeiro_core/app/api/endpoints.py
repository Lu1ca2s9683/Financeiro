from ninja import Router, Schema, Field
from ninja.errors import HttpError
from typing import List, Optional
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.db import transaction
from datetime import date
import traceback

# Importações dos modelos e serviços
from ..models.entidades import (
    ContaPagar, 
    CategoriaDespesa, 
    FechamentoMensal,
    TaxaMaquininha, 
    PerfilTaxaCartao,
    Fornecedor,
    ContaBancaria,
    MovimentacaoCaixa
)
from ...infrastructure.vendas_client import VendasClientSQL, VendasAPIClientMock
from ...domain.services import ProcessadorFechamento, FaturamentoItemDTO
from .security import AuthBearer, check_permission

# Instância do Router
router = Router(auth=AuthBearer())

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

    def agrupar_despesas_por_grupo_contabil(self, loja_id, mes, ano):
        from django.db.models import Sum
        qs = ContaPagar.objects.filter(
            loja_id_externo=loja_id,
            data_competencia__month=mes,
            data_competencia__year=ano
        ).exclude(status='CANCELADO').values('categoria__grupo_contabil').annotate(total=Sum('valor_liquido'))

        return {item['categoria__grupo_contabil']: item['total'] for item in qs if item['categoria__grupo_contabil']}

# ==============================================================================
# 2. SCHEMAS (DATA TRANSFER OBJECTS)
# ==============================================================================

# --- Schemas de Categoria ---
class CategoriaIn(Schema):
    nome: str
    grupo_contabil: str
    ativa: bool = True

class CategoriaOut(Schema):
    id: int
    nome: str
    grupo_contabil: str
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
    loja_id: Optional[int] = None # Ignorado no backend, usado pelo contexto do token
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
    dias_para_vencimento: Optional[int] = None
    is_vencendo: bool = False
    is_atrasado: bool = False

    @staticmethod
    def resolve_dias_para_vencimento(obj):
        if obj.status == 'PAGO':
            return None
        return (obj.data_vencimento - date.today()).days

    @staticmethod
    def resolve_is_vencendo(obj):
        if obj.status == 'PAGO':
            return False
        dias = (obj.data_vencimento - date.today()).days
        return 0 <= dias <= 7

    @staticmethod
    def resolve_is_atrasado(obj):
        if obj.status == 'PAGO':
            return False
        # Se o status já é ATRASADO ou se venceu e não está pago
        if obj.status == 'ATRASADO':
            return True
        return obj.data_vencimento < date.today()

class DespesaDetailOut(DespesaOut):
    valor_bruto: Decimal
    valor_desconto: Decimal
    valor_acrescimo: Decimal
    data_vencimento: date
    fornecedor_id: Optional[int] = None
    loja_id_externo: int

class StatusUpdate(Schema):
    status: str

# --- Schemas de Conta Bancária ---
class ContaBancariaIn(Schema):
    nome: str
    tipo: str
    banco_codigo: Optional[str] = ""
    agencia: Optional[str] = ""
    conta: Optional[str] = ""
    saldo_inicial: Decimal = Decimal('0.00')

class ContaBancariaOut(Schema):
    id: int
    nome: str
    tipo: str
    banco_codigo: str
    agencia: str
    conta: str
    saldo_inicial: Decimal
    saldo_atual: Decimal
    ativo: bool

class DashboardResumoOut(Schema):
    percentual_pago: float
    percentual_atrasado: float
    percentual_previsto: float
    total_despesas_mes: int
    despesas_vencendo_semana: int
    despesas_atrasadas: int
    saude_financeira: str  # 'SAUDAVEL', 'ATENCAO', 'CRITICO'
    mensagem_assistente: str

    # Adicionando os mesmos campos do DRE no resumo do dashboard (opcional, já que o frontend consome de FechamentoOut)
    # Mas como o prompt pede "Refatore a lógica de getFechamento e getDashboardResumo para classificar as despesas"
    # vamos injetá-los no DashboardResumoOut se o frontend quiser.

# --- Schemas de Fechamento ---
class FechamentoOut(Schema):
    loja_id: int = Field(..., alias="loja_id_externo") 
    mes: int
    ano: int

    receita_bruta: Decimal
    total_dinheiro: Decimal = Decimal('0.00')
    total_cartao: Decimal = Decimal('0.00')
    total_pix: Decimal = Decimal('0.00')

    impostos: Decimal = Decimal('0.00')
    receita_liquida: Decimal
    custos_produtos: Decimal = Decimal('0.00')
    lucro_bruto: Decimal
    despesas_operacionais: Decimal = Decimal('0.00')
    resultado_operacional: Decimal
    total_taxas: Decimal = Decimal('0.00')
    despesas_financeiras: Decimal = Decimal('0.00')
    lucro_liquido: Decimal

    status: str

    class Config:
        from_attributes = True 

# ==============================================================================
# 3. ENDPOINTS
# ==============================================================================

# --- DASHBOARD ---

@router.get("/dashboard/resumo/{loja_id}/{mes}/{ano}", response=DashboardResumoOut)
def obter_resumo_dashboard(request, loja_id: int, mes: int, ano: int):
    """Retorna dados agregados para o dashboard."""
    print(f"DEBUG: Endpoint Dashboard acessado pelo usuário {request.auth}")
    check_permission(request, loja_id)

    # Nota: A classificação de despesas pelo grupo contábil (DRE) agora
    # é manipulada rigorosamente no getFechamento (`calcular_fechamento`).
    # O dashboard do frontend consome e exibe a cascata matemática e totais
    # vindo exclusivamente do endpoint de fechamento (veja page.tsx: dados = api.getFechamento).
    # O resumo foca no status temporal (vencimentos/saúde) e assistente.
    despesas = ContaPagar.objects.filter(
        loja_id_externo=loja_id,
        data_competencia__month=mes,
        data_competencia__year=ano
    ).exclude(status='CANCELADO')

    total = despesas.count()
    if total == 0:
        return {
            "percentual_pago": 0.0,
            "percentual_atrasado": 0.0,
            "percentual_previsto": 0.0,
            "total_despesas_mes": 0,
            "despesas_vencendo_semana": 0,
            "despesas_atrasadas": 0,
            "saude_financeira": "SAUDAVEL", # Sem dívidas é saudável
            "mensagem_assistente": "Nenhuma despesa lançada para este período."
        }

    pagas = despesas.filter(status='PAGO').count()
    atrasadas = despesas.filter(status='ATRASADO').count()
    # Considera também as que venceram e ainda estão como PREVISTO
    hoje = date.today()
    atrasadas_reais = 0
    previstas = 0
    vencendo_semana = 0

    for d in despesas:
        if d.status == 'PAGO':
            continue

        # Lógica de atraso
        if d.status == 'ATRASADO' or d.data_vencimento < hoje:
            atrasadas_reais += 1
        else:
            previstas += 1
            # Vencendo na semana (0 a 7 dias)
            dias = (d.data_vencimento - hoje).days
            if 0 <= dias <= 7:
                vencendo_semana += 1

    perc_pago = (pagas / total) * 100
    perc_atrasado = (atrasadas_reais / total) * 100
    perc_previsto = (previstas / total) * 100

    # Saúde Financeira
    if perc_pago >= 80:
        saude = "SAUDAVEL"
    elif perc_pago >= 50:
        saude = "ATENCAO"
    else:
        saude = "CRITICO"

    # Assistente Contextual
    msg = ""
    if vencendo_semana > 0:
        msg = f"Atenção: Você tem {vencendo_semana} despesa(s) vencendo nos próximos 7 dias."
    elif atrasadas_reais > 0:
        msg = f"Cuidado: Existem {atrasadas_reais} despesa(s) em atraso neste mês."
    elif perc_pago > 90:
        msg = f"Excelente! {int(perc_pago)}% das despesas deste mês já foram quitadas."
    elif perc_previsto > 50:
        msg = "Mês em andamento. Mantenha o controle dos vencimentos."
    else:
        msg = "Saúde financeira estável. Nenhuma pendência urgente."

    return {
        "percentual_pago": round(perc_pago, 1),
        "percentual_atrasado": round(perc_atrasado, 1),
        "percentual_previsto": round(perc_previsto, 1),
        "total_despesas_mes": total,
        "despesas_vencendo_semana": vencendo_semana,
        "despesas_atrasadas": atrasadas_reais,
        "saude_financeira": saude,
        "mensagem_assistente": msg
    }

# --- CONTAS BANCÁRIAS (CRUD TESOURARIA) ---

@router.get("/contas/", response=List[ContaBancariaOut], auth=AuthBearer())
def listar_contas(request):
    """Lista contas bancárias e cofres da loja ativa."""
    active_loja_id = request.active_loja_id
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    return ContaBancaria.objects.filter(loja_id_externo=active_loja_id, ativo=True)

@router.post("/contas/", response=ContaBancariaOut, auth=AuthBearer())
def criar_conta(request, payload: ContaBancariaIn):
    """Cria uma nova conta ou caixa físico para a loja ativa."""
    active_loja_id = request.active_loja_id
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    nova_conta = ContaBancaria.objects.create(
        nome=payload.nome,
        tipo=payload.tipo,
        banco_codigo=payload.banco_codigo,
        agencia=payload.agencia,
        conta=payload.conta,
        saldo_inicial=payload.saldo_inicial,
        saldo_atual=payload.saldo_inicial, # Saldo atual começa igual ao inicial
        loja_id_externo=active_loja_id
    )
    return nova_conta

# --- CATEGORIAS (CRUD) ---

@router.get("/categorias/", response=List[CategoriaOut], auth=AuthBearer())
def listar_categorias(request):
    """Lista todas as categorias de despesa ativas."""
    return CategoriaDespesa.objects.filter(ativa=True)

@router.post("/categorias/", response=CategoriaOut, auth=AuthBearer())
def criar_categoria(request, payload: CategoriaIn):
    """Cria uma nova categoria."""
    return CategoriaDespesa.objects.create(**payload.dict())

@router.put("/categorias/{categoria_id}", response=CategoriaOut, auth=AuthBearer())
def editar_categoria(request, categoria_id: int, payload: CategoriaIn):
    """Edita nome ou status da categoria."""
    cat = get_object_or_404(CategoriaDespesa, id=categoria_id)
    cat.nome = payload.nome
    cat.grupo_contabil = payload.grupo_contabil
    cat.ativa = payload.ativa
    cat.save()
    return cat

@router.delete("/categorias/{categoria_id}", auth=AuthBearer())
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
    if loja_id:
        check_permission(request, loja_id)

    qs = PerfilTaxaCartao.objects.filter(ativo=True).prefetch_related('taxas')
    if loja_id:
        qs = qs.filter(loja_id_externo=loja_id)
    return qs

# --- DESPESAS (CRUD) ---

@router.get("/despesas/", response=List[DespesaOut])
def listar_despesas(
    request, 
    loja_id: Optional[int] = None, # Ignorado no backend, usado do token
    mes: Optional[int] = None,
    ano: Optional[int] = None
):
    """Lista despesas, opcionalmente filtrando por loja e competência."""
    active_loja_id = request.active_loja_id
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    qs = ContaPagar.objects.filter(loja_id_externo=active_loja_id).select_related('categoria')
    
    if mes and ano:
        qs = qs.filter(data_competencia__month=mes, data_competencia__year=ano)
        
    return qs

@router.get("/despesas/{despesa_id}", response=DespesaDetailOut)
def obter_despesa(request, despesa_id: int):
    """Retorna detalhes de uma despesa."""
    active_loja_id = request.active_loja_id
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    despesa = get_object_or_404(ContaPagar, id=despesa_id, loja_id_externo=active_loja_id)
    return despesa

@router.patch("/despesas/{despesa_id}/status", response=DespesaOut)
def atualizar_status_despesa(request, despesa_id: int, payload: StatusUpdate):
    """Atualiza o status da despesa, validando fechamento."""
    active_loja_id = request.active_loja_id
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    despesa = get_object_or_404(ContaPagar, id=despesa_id, loja_id_externo=active_loja_id)

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
    try:
        print("DEBUG PAYLOAD DE ENTRADA:", payload.dict())

        # Pega a loja do token de segurança que já configuramos
        loja_id_do_token = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
        print("DEBUG LOJA DO TOKEN:", loja_id_do_token)

        if not loja_id_do_token:
            raise HttpError(400, "Nenhuma loja ativa no contexto")

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
            loja_id_externo=loja_id_do_token,
            categoria=categoria,
            fornecedor=fornecedor,
            valor_bruto=payload.valor,
            data_competencia=payload.data_competencia,
            data_vencimento=payload.data_vencimento,
            criado_por_id=getattr(request, 'user_id', None)
        )
        return despesa

    except Exception as e:
        print("======= ERRO AO SALVAR DESPESA =======")
        traceback.print_exc()
        print("======================================")
        raise HttpError(500, str(e))

@router.put("/despesas/{despesa_id}", response=DespesaOut)
def editar_despesa(request, despesa_id: int, payload: DespesaIn):
    """Atualiza uma despesa e recalcula valores."""
    active_loja_id = request.active_loja_id
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    despesa = get_object_or_404(ContaPagar, id=despesa_id, loja_id_externo=active_loja_id)

    # Validar fechamento (Data Atual)
    fechamento_atual = FechamentoMensal.objects.filter(
        loja_id_externo=active_loja_id,
        mes=despesa.data_competencia.month,
        ano=despesa.data_competencia.year
    ).first()

    if fechamento_atual and fechamento_atual.status == 'CONCLUIDO':
        raise HttpError(400, f"Não é possível editar despesa de mês fechado ({despesa.data_competencia.strftime('%m/%Y')}).")

    # Validar fechamento (Nova Data - se mudou)
    if payload.data_competencia != despesa.data_competencia:
        fechamento_novo = FechamentoMensal.objects.filter(
            loja_id_externo=active_loja_id,
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
    active_loja_id = request.active_loja_id
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    despesa = get_object_or_404(ContaPagar, id=despesa_id, loja_id_externo=active_loja_id)
    despesa.delete()
    return {"success": True, "message": f"Despesa {despesa_id} excluída."}

# --- FECHAMENTO ---

@router.post("/fechamento/calcular/{loja_id}/{mes}/{ano}", response=FechamentoOut)
def calcular_fechamento(request, loja_id: int, mes: int, ano: int):
    """Calcula e persiste o fechamento mensal."""
    active_loja_id = request.active_loja_id
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    # Assegura que o parâmetro de loja_id no endpoint corresponde à loja ativa ou ignora o parâmetro
    # e força a operação para a loja ativa do token, blindando a integridade.
    target_loja = active_loja_id

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
    dados_vendas = vendas_client.get_faturamento_por_loja(target_loja, mes, ano)
    resultado = processador.executar_fechamento(target_loja, mes, ano, dados_vendas)

    # 3. Persiste Resultado
    with transaction.atomic():
        fechamento, created = FechamentoMensal.objects.update_or_create(
            loja_id_externo=target_loja,
            mes=mes,
            ano=ano,
            defaults={
                'faturamento_bruto': resultado.faturamento_bruto,
                'total_taxas': resultado.total_taxas,
                'receita_liquida': resultado.receita_liquida,
                'total_despesas': resultado.impostos + resultado.custos_produtos + resultado.despesas_operacionais + resultado.despesas_financeiras,
                'resultado_operacional': resultado.resultado_operacional,
                'status': 'ABERTO',
                'dados_auditoria_snapshot': resultado.snapshot_dados
            }
        )

    # Dicionário exato esperado pelo Schema FechamentoOut
    resposta_dre = {
        "loja_id_externo": target_loja,
        "mes": mes,
        "ano": ano,
        "receita_bruta": resultado.faturamento_bruto or Decimal('0.00'),
        "total_dinheiro": resultado.total_dinheiro or Decimal('0.00'),
        "total_cartao": resultado.total_cartao or Decimal('0.00'),
        "total_pix": resultado.total_pix or Decimal('0.00'),
        "impostos": resultado.impostos or Decimal('0.00'),
        "receita_liquida": resultado.receita_liquida or Decimal('0.00'),
        "custos_produtos": resultado.custos_produtos or Decimal('0.00'),
        "lucro_bruto": resultado.lucro_bruto or Decimal('0.00'),
        "despesas_operacionais": resultado.despesas_operacionais or Decimal('0.00'),
        "resultado_operacional": resultado.resultado_operacional or Decimal('0.00'),
        "total_taxas": resultado.total_taxas or Decimal('0.00'),
        "despesas_financeiras": resultado.despesas_financeiras or Decimal('0.00'),
        "lucro_liquido": resultado.lucro_liquido or Decimal('0.00'),
        "status": fechamento.status
    }

    return resposta_dre