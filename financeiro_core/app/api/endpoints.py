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
    ContaPagar, RateioDespesa,
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
            data_transacao__month=mes,
            data_transacao__year=ano
        ).aggregate(Sum('valor_liquido'))['valor_liquido__sum']
        return val or Decimal('0.00')

    def agrupar_despesas_por_grupo_contabil(self, loja_id, mes, ano):
        from django.db.models import Sum
        qs = ContaPagar.objects.filter(
            loja_id_externo=loja_id,
            data_competencia__month=mes,
            data_transacao__year=ano
        ).values('categoria__grupo_contabil').annotate(total=Sum('valor_liquido'))

        return {item['categoria__grupo_contabil']: item['total'] for item in qs if item['categoria__grupo_contabil']}

# ==============================================================================
# 2. SCHEMAS (DATA TRANSFER OBJECTS)
# ==============================================================================

# --- Schemas de Categoria ---
class CategoriaIn(Schema):
    nome: str
    grupo_contabil: str
    ativa: bool = True

class RateioIn(Schema):
    descricao: str
    valor: Decimal
    categoria_id: Optional[int] = None

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
    data_transacao: date
    rateios: List[RateioIn] = []
    fornecedor_id: Optional[int] = None

class DespesaOut(Schema):
    id: int
    descricao: str
    valor_liquido: Decimal
    data_transacao: Optional[date] = None
    data_competencia: date
    categoria: CategoriaOut = None 


class DespesaDetailOut(DespesaOut):
    valor_bruto: Decimal
    valor_desconto: Decimal
    valor_acrescimo: Decimal
    data_transacao: date
    rateios: List[RateioIn] = []
    fornecedor_id: Optional[int] = None
    loja_id_externo: int

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

class TransferenciaIn(Schema):
    conta_origem_id: int
    conta_destino_id: int
    valor: Decimal
    data_ocorrencia: date
    descricao: str

class DashboardResumoOut(Schema):
    percentual_pago: float
    percentual_atrasado: float
    percentual_previsto: float
    total_despesas_mes: float
    despesas_vencendo_semana: int
    despesas_atrasadas: int
    saude_financeira: str  # 'SAUDAVEL', 'ATENCAO', 'CRITICO'
    mensagem_assistente: str

# --- Schemas de Fechamento ---
class FechamentoOut(Schema):
    loja_id_externo: int  # Alterado para casar perfeitamente com o retorno e evitar ValidationError
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

    data_transacao: Optional[date] = None

    class Config:
        from_attributes = True 

# ==============================================================================
# 3. ENDPOINTS
# ==============================================================================

# --- DASHBOARD ---

@router.get("/dashboard/resumo/{loja_id}/{mes}/{ano}", response=DashboardResumoOut)
def obter_resumo_dashboard(request, loja_id: int, mes: int, ano: int):
    """Retorna dados agregados para o dashboard usando Regime de Caixa (data_transacao)."""
    print(f"DEBUG: Endpoint Dashboard acessado pelo usuário {request.auth}")
    check_permission(request, loja_id)

    despesas = ContaPagar.objects.filter(
        loja_id_externo=loja_id,
        data_transacao__month=mes,
        data_transacao__year=ano
    ).prefetch_related('splits')

    total = despesas.count()
    if total == 0:
        return {
            "percentual_pago": 100.0,
            "percentual_atrasado": 0.0,
            "percentual_previsto": 0.0,
            "total_despesas_mes": 0,
            "despesas_vencendo_semana": 0,
            "despesas_atrasadas": 0,
            "saude_financeira": "SAUDAVEL",
            "mensagem_assistente": "Nenhuma despesa lançada no regime de caixa para este período."
        }

    total_despesas_mes = 0

    for d in despesas:
        if d.splits.exists():
            for split in d.splits.all():
                total_despesas_mes += float(split.valor)
        else:
            total_despesas_mes += float(d.valor_liquido)

    # Como filtramos por data_transacao, consideramos tudo como pago/caixa.
    perc_pago = 100.0
    perc_atrasado = 0.0
    perc_previsto = 0.0

    return {
        "percentual_pago": round(perc_pago, 1),
        "percentual_atrasado": round(perc_atrasado, 1),
        "percentual_previsto": round(perc_previsto, 1),
        "total_despesas_mes": round(total_despesas_mes, 2),
        "despesas_vencendo_semana": 0,
        "despesas_atrasadas": 0,
        "saude_financeira": "SAUDAVEL",
        "mensagem_assistente": "Resumo calculado em regime de caixa com sucesso."
    }
def listar_contas(request):
    """Lista contas bancárias e cofres da loja ativa."""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    return ContaBancaria.objects.filter(loja_id_externo=active_loja_id, ativo=True)

@router.get("/contas/", response=List[ContaBancariaOut])
def listar_contas(request):
    """Lista as contas bancárias da loja ativa."""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")
    return ContaBancaria.objects.filter(loja_id_externo=active_loja_id, ativo=True)

@router.post("/contas/", response=ContaBancariaOut, auth=AuthBearer())
def criar_conta(request, payload: ContaBancariaIn):
    """Cria uma nova conta ou caixa físico para a loja ativa."""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    nova_conta = ContaBancaria.objects.create(
        nome=payload.nome,
        tipo=payload.tipo,
        banco_codigo=payload.banco_codigo,
        agencia=payload.agencia,
        conta=payload.conta,
        saldo_inicial=payload.saldo_inicial,
        saldo_atual=payload.saldo_inicial,
        loja_id_externo=active_loja_id
    )
    return nova_conta

@router.post("/contas/transferencia", auth=AuthBearer())
def registrar_transferencia(request, payload: TransferenciaIn):
    """Realiza uma transferência segura entre contas (Sangria/Depósito)."""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    if payload.conta_origem_id == payload.conta_destino_id:
        raise HttpError(400, "A conta de origem e destino não podem ser as mesmas.")

    conta_origem = get_object_or_404(ContaBancaria, id=payload.conta_origem_id, loja_id_externo=active_loja_id, ativo=True)
    conta_destino = get_object_or_404(ContaBancaria, id=payload.conta_destino_id, loja_id_externo=active_loja_id, ativo=True)

    if payload.valor <= 0:
        raise HttpError(400, "O valor da transferência deve ser maior que zero.")

    user_id = getattr(request, 'user_id', None)

    with transaction.atomic():
        MovimentacaoCaixa.objects.create(
            conta=conta_origem,
            tipo_movimentacao='TRANSFERENCIA_SAIDA',
            descricao=payload.descricao,
            valor=payload.valor,
            data_ocorrencia=payload.data_ocorrencia,
            loja_id_externo=active_loja_id,
            criado_por_id=user_id
        )

        MovimentacaoCaixa.objects.create(
            conta=conta_destino,
            tipo_movimentacao='TRANSFERENCIA_ENTRADA',
            descricao=payload.descricao,
            valor=payload.valor,
            data_ocorrencia=payload.data_ocorrencia,
            loja_id_externo=active_loja_id,
            criado_por_id=user_id
        )

    return {"success": True, "message": "Transferência realizada com sucesso."}

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
    loja_id: Optional[int] = None,
    mes: Optional[int] = None,
    ano: Optional[int] = None
):
    """Lista despesas, opcionalmente filtrando por loja e competência."""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    qs = ContaPagar.objects.filter(loja_id_externo=active_loja_id).select_related('categoria')
    
    if mes and ano:
        qs = qs.filter(data_transacao__month=mes, data_transacao__year=ano)
        
    return qs

@router.get("/despesas/{despesa_id}", response=DespesaDetailOut)
def obter_despesa(request, despesa_id: int):
    """Retorna detalhes de uma despesa."""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    despesa = get_object_or_404(ContaPagar, id=despesa_id, loja_id_externo=active_loja_id)
    return despesa


@router.post("/despesas/", response=DespesaOut)
def criar_despesa(request, payload: DespesaIn):
    """Cria uma nova conta a pagar."""
    try:
        loja_id_do_token = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)

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
            data_transacao=payload.data_transacao,
            criado_por_id=getattr(request, 'user_id', None)
        )
        for r in payload.rateios:
            cat_id = r.categoria_id if r.categoria_id else categoria.id
            cat_rateio = CategoriaDespesa.objects.get(id=cat_id)
            RateioDespesa.objects.create(
                despesa=despesa,
                descricao=r.descricao,
                valor=r.valor,
                categoria=cat_rateio
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
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    despesa = get_object_or_404(ContaPagar, id=despesa_id, loja_id_externo=active_loja_id)

    fechamento_atual = FechamentoMensal.objects.filter(
        loja_id_externo=active_loja_id,
        mes=despesa.data_competencia.month,
        ano=despesa.data_competencia.year
    ).first()

    if fechamento_atual and fechamento_atual.status == 'CONCLUIDO':
        raise HttpError(400, f"Não é possível editar despesa de mês fechado ({despesa.data_competencia.strftime('%m/%Y')}).")

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
    despesa.data_transacao = payload.data_transacao
    despesa.save()
    
    despesa.splits.all().delete()
    for r in payload.rateios:
        cat_id = r.categoria_id if r.categoria_id else categoria.id
        cat_rateio = CategoriaDespesa.objects.get(id=cat_id)
        RateioDespesa.objects.create(
            despesa=despesa,
            descricao=r.descricao,
            valor=r.valor,
            categoria=cat_rateio
        )

    return despesa

@router.delete("/despesas/{despesa_id}")
def excluir_despesa(request, despesa_id: int):
    """Exclui uma despesa."""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    despesa = get_object_or_404(ContaPagar, id=despesa_id, loja_id_externo=active_loja_id)
    despesa.delete()
    return {"success": True, "message": f"Despesa {despesa_id} excluída."}

# --- FECHAMENTO ---

@router.post("/fechamento/calcular/{loja_id}/{mes}/{ano}", response=FechamentoOut)
def calcular_fechamento(request, loja_id: int, mes: int, ano: int):
    """Calcula e persiste o fechamento mensal."""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    # Assegura que o parâmetro de loja_id no endpoint corresponde à loja ativa ou ignora o parâmetro
    # e força a operação para a loja ativa do token, blindando a integridade.
    target_loja = active_loja_id

    # 1. Instancia dependências (SQL Real ou Mock)
    """Calcula e persiste o fechamento mensal, blindado contra quebras silenciosas."""
    try:
        active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
        if not active_loja_id:
            raise HttpError(400, "Nenhuma loja ativa no contexto")

        target_loja = active_loja_id

        try:
            vendas_client = VendasClientSQL()
        except Exception as e:
            print(f"Erro conexão SQL: {e}")
            vendas_client = VendasAPIClientMock()

        repo_taxas = DjangoRepositorioTaxas()
        repo_despesas = DjangoRepositorioDespesas()

        processador = ProcessadorFechamento(repo_taxas, repo_despesas)
        dados_vendas = vendas_client.get_faturamento_por_loja(target_loja, mes, ano)
        resultado = processador.executar_fechamento(target_loja, mes, ano, dados_vendas)

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
        
    except Exception as e:
        print("======= ERRO FATAL NO FECHAMENTO =======")
        traceback.print_exc()
        print("========================================")
        raise HttpError(500, f"Erro interno detectado: {str(e)}")

from ninja import File
from ninja.files import UploadedFile
from financeiro_core.app.services.ofx_parser import OfxParserService
from datetime import date

class ExtratoItemOut(Schema):
    data_transacao: date
    descricao_original: str
    valor: Decimal
    tipo: str
    categoria_sugerida_id: int | None = None

@router.post("/import-statement/", response=list[ExtratoItemOut])
def importar_extrato(request, file: UploadedFile = File(...)):
    """Importa um arquivo OFX/OFC e retorna as transações com sugestões de categoria."""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    content = file.read().decode('utf-8', errors='ignore')
    transactions = OfxParserService.parse(content)

    for t in transactions:
        t['categoria_sugerida_id'] = OfxParserService.adivinhar_categoria(t['descricao_original'], active_loja_id)

    return transactions

@router.post("/extrato/importar-despesas/{loja_id}")
@router.post("/extrato/importar-despesas/{loja_id}/")
def importar_extrato_despesas(request, loja_id: int, file: UploadedFile = File(...)):
    """Importa um arquivo OFX/OFC filtrando estritamente para SAIDAS."""
    import re

    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id or int(active_loja_id) != loja_id:
        raise HttpError(400, "Loja inválida no contexto")

    check_permission(request, loja_id)

    try:
        conteudo = file.read().decode('latin-1', errors='ignore')
    except Exception as e:
        raise HttpError(400, "Erro ao ler a codificação do ficheiro.")

    transacoes_negativas = []

    blocos = conteudo.split('<STMTTRN>')

    for bloco in blocos[1:]:
        try:
            dt_match = re.search(r'<DTPOSTED>(\d{8})', bloco)
            amt_match = re.search(r'<TRNAMT>([\-\d\.]+)', bloco)
            memo_match = re.search(r'<MEMO>(.*)', bloco)

            if dt_match and amt_match and memo_match:
                valor = float(amt_match.group(1))

                if valor < 0:
                    data_str = dt_match.group(1)
                    data_formatada = f"{data_str[0:4]}-{data_str[4:6]}-{data_str[6:8]}"

                    descricao = memo_match.group(1).strip()

                    categoria_sug = OfxParserService.adivinhar_categoria(descricao, active_loja_id)

                    transacoes_negativas.append({
                        "data_transacao": data_formatada,
                        "descricao_original": descricao,
                        "valor": valor,
                        "tipo": "SAIDA",
                        "categoria_sugerida_id": categoria_sug
                    })
        except Exception:
            continue

    return transacoes_negativas
