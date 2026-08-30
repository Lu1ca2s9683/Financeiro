import json

from ninja import File, Router, Schema, UploadedFile

class DashboardResumoOut(Schema):
    percentual_pago: float
    percentual_atrasado: float
    percentual_previsto: float
    total_despesas_mes: float
    despesas_vencendo_semana: int
    despesas_atrasadas: int
    saude_financeira: str
    mensagem_assistente: str

from ninja.errors import HttpError
from typing import List, Optional
from decimal import Decimal
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.db import transaction
from django.core.serializers.json import DjangoJSONEncoder
from datetime import date, datetime, time
from django.utils import timezone

# Importações dos modelos e serviços
from ..models.entidades import (
    ContaPagar, RateioDespesa,
    CategoriaDespesa, 
    FechamentoMensal,
    PerfilTaxaCartao,
    Fornecedor,
    ContaBancaria,
    MovimentacaoCaixa
)
from .security import AuthBearer, check_permission

# Instância do Router
router = Router(auth=AuthBearer())

@router.get("/dashboard/resumo/{loja_id}/{mes}/{ano}", response=DashboardResumoOut)
def obter_resumo_dashboard(request, loja_id: int, mes: int, ano: int):
    """Retorna dados agregados para o dashboard usando Regime de Caixa (data_transacao)."""
    print(f"DEBUG: Endpoint Dashboard acessado pelo usuário {request.auth}")
    check_permission(request, loja_id)
    if not (1 <= mes <= 12):
        raise HttpError(400, "Mês inválido.")

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

    total_despesas_mes = sum(
        (despesa.valor_liquido for despesa in despesas), Decimal('0.00')
    )

    # ContaPagar não possui vencimento. Não fabricamos atraso usando competência
    # ou data da transação; essas métricas ficam neutras até existir dado real.
    perc_pago = 100.0
    perc_atrasado = 0.0
    perc_previsto = 0.0

    return {
        "percentual_pago": round(perc_pago, 1),
        "percentual_atrasado": round(perc_atrasado, 1),
        "percentual_previsto": round(perc_previsto, 1),
        "total_despesas_mes": float(total_despesas_mes),
        "despesas_vencendo_semana": 0,
        "despesas_atrasadas": 0,
        "saude_financeira": "SAUDAVEL",
        "mensagem_assistente": "Resumo calculado em regime de caixa com sucesso."
    }


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

class ContaBancariaIn(Schema):
    nome: str
    tipo: str
    banco_codigo: str = ''
    agencia: str = ''
    conta: str = ''
    saldo_inicial: Decimal = Decimal('0.00')

@router.get("/contas/", response=List[ContaBancariaOut], auth=AuthBearer())
def listar_contas(request):
    """Lista contas bancárias e cofres ativos da loja autenticada."""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    return ContaBancaria.objects.filter(
        loja_id_externo=active_loja_id,
        ativo=True,
    ).order_by("id")

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

class TransferenciaIn(Schema):
    conta_origem_id: int
    conta_destino_id: int
    valor: Decimal
    data: date
    descricao: str


def _selecionar_contas_transferencia_bloqueadas(loja_id, conta_ids):
    """Bloqueia as contas em ordem estável para evitar lost update/deadlock."""
    contas = list(
        ContaBancaria.objects.select_for_update()
        .filter(id__in=conta_ids, loja_id_externo=loja_id, ativo=True)
        .order_by('id')
    )
    if len(contas) != len(set(conta_ids)):
        raise Http404("Conta bancária não encontrada para a loja ativa.")
    return contas

@router.post("/contas/transferencia", auth=AuthBearer())
def registrar_transferencia(request, payload: TransferenciaIn):
    """Realiza uma transferência segura entre contas (Sangria/Depósito)."""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    if payload.conta_origem_id == payload.conta_destino_id:
        raise HttpError(400, "A conta de origem e destino não podem ser as mesmas.")

    if payload.valor <= 0:
        raise HttpError(400, "O valor da transferência deve ser maior que zero.")

    user_id = getattr(request, 'user_id', None)
    data_ocorrencia = timezone.make_aware(
        datetime.combine(payload.data, time.min),
        timezone.get_current_timezone(),
    )

    with transaction.atomic():
        contas = _selecionar_contas_transferencia_bloqueadas(
            active_loja_id,
            [payload.conta_origem_id, payload.conta_destino_id],
        )
        contas_por_id = {conta.id: conta for conta in contas}
        conta_origem = contas_por_id[payload.conta_origem_id]
        conta_destino = contas_por_id[payload.conta_destino_id]

        MovimentacaoCaixa.objects.create(
            conta=conta_origem,
            tipo_movimentacao='TRANSFERENCIA_SAIDA',
            descricao=payload.descricao,
            valor=payload.valor,
            data_ocorrencia=data_ocorrencia,
            loja_id_externo=active_loja_id,
            criado_por_id=user_id
        )

        MovimentacaoCaixa.objects.create(
            conta=conta_destino,
            tipo_movimentacao='TRANSFERENCIA_ENTRADA',
            descricao=payload.descricao,
            valor=payload.valor,
            data_ocorrencia=data_ocorrencia,
            loja_id_externo=active_loja_id,
            criado_por_id=user_id
        )

    return {"success": True, "message": "Transferência realizada com sucesso."}


class ExtratoItemOut(Schema):
    data_transacao: date
    descricao_original: str
    valor: Decimal
    tipo: str
    categoria_sugerida_id: Optional[int] = None


@router.post(
    "/extrato/importar-despesas/{loja_id}/",
    response=List[ExtratoItemOut],
    auth=AuthBearer(),
)
def importar_extrato_despesas(request, loja_id: int, file: File[UploadedFile]):
    """Lê um OFX/OFC sem persistir lançamentos e respeita a loja autenticada."""
    check_permission(request, loja_id)

    raw_content = file.read()
    try:
        file_content = raw_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        file_content = raw_content.decode("latin-1")

    from financeiro_core.app.services.ofx_parser import OfxParserService

    transactions = OfxParserService.parse(file_content)
    if not transactions:
        raise HttpError(400, "Arquivo OFX/OFC inválido ou sem transações válidas.")

    for item in transactions:
        item["categoria_sugerida_id"] = (
            OfxParserService.adivinhar_categoria(item["descricao_original"], loja_id)
            if item["tipo"] == "SAIDA"
            else None
        )

    return transactions

# --- CATEGORIAS (CRUD) ---

    id: int
    nome: str
    grupo_contabil: str
    ativa: bool

class CategoriaOut(Schema):
    id: int
    nome: str
    grupo_contabil: str
    ativa: bool

class CategoriaIn(Schema):
    nome: str
    grupo_contabil: str
    ativa: bool = True

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

class TaxaMaquininhaOut(Schema):
    tipo: str
    bandeira: str
    taxa_percentual: Decimal
    taxa_fixa: Decimal
    dias_para_recebimento: int

class PerfilTaxaOut(Schema):
    id: int
    nome: str
    data_inicio_vigencia: date
    ativo: bool
    taxas: List[TaxaMaquininhaOut] = []

class PerfilTaxaIn(Schema):
    nome: str
    data_inicio_vigencia: date
    ativo: bool = True

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

class RateioIn(Schema):
    descricao: str
    valor: Decimal
    categoria_id: Optional[int] = None

class DespesaIn(Schema):
    descricao: str
    loja_id: Optional[int] = None
    categoria_id: int
    valor: Decimal
    data_competencia: date
    data_transacao: date
    rateios: List[RateioIn] = []
    fornecedor_id: Optional[int] = None

class RateioOut(Schema):
    id: int
    descricao: str
    valor: Decimal
    categoria_id: Optional[int]

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
    splits: List[RateioOut] = []


def _garantir_periodo_caixa_aberto(loja_id: int, data_transacao: date):
    if data_transacao is None:
        return
    if FechamentoMensal.objects.filter(
        loja_id_externo=loja_id,
        mes=data_transacao.month,
        ano=data_transacao.year,
        status='CONCLUIDO',
    ).exists():
        raise HttpError(
            409,
            f"Período de caixa concluído ({data_transacao.strftime('%m/%Y')}).",
        )


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
    loja_id_do_token = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)

    if not loja_id_do_token:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    _garantir_periodo_caixa_aberto(loja_id_do_token, payload.data_transacao)
    categoria = get_object_or_404(CategoriaDespesa, id=payload.categoria_id)
    fornecedor = (
        get_object_or_404(Fornecedor, id=payload.fornecedor_id)
        if payload.fornecedor_id
        else None
    )

    with transaction.atomic():
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
            cat_rateio = get_object_or_404(CategoriaDespesa, id=cat_id)
            RateioDespesa.objects.create(
                despesa=despesa,
                descricao=r.descricao,
                valor=r.valor,
                categoria=cat_rateio
            )
    return despesa

@router.put("/despesas/{despesa_id}", response=DespesaOut)
def editar_despesa(request, despesa_id: int, payload: DespesaIn):
    """Atualiza uma despesa e recalcula valores."""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    despesa = get_object_or_404(ContaPagar, id=despesa_id, loja_id_externo=active_loja_id)

    _garantir_periodo_caixa_aberto(active_loja_id, despesa.data_transacao)
    if payload.data_transacao != despesa.data_transacao:
        _garantir_periodo_caixa_aberto(active_loja_id, payload.data_transacao)

    if not CategoriaDespesa.objects.filter(id=payload.categoria_id).exists():
        raise HttpError(404, f"Categoria {payload.categoria_id} não encontrada.")
    categoria = CategoriaDespesa.objects.get(id=payload.categoria_id)

    fornecedor = None
    if payload.fornecedor_id:
        fornecedor = get_object_or_404(Fornecedor, id=payload.fornecedor_id)

    with transaction.atomic():
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
            cat_rateio = get_object_or_404(CategoriaDespesa, id=cat_id)
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
    _garantir_periodo_caixa_aberto(active_loja_id, despesa.data_transacao)
    despesa.delete()
    return {"success": True, "message": f"Despesa {despesa_id} excluída."}

# --- FECHAMENTO ---

@router.get("/dre/{loja_id}/{mes}/{ano}")
def get_dre(request, loja_id: int, mes: int, ano: int):
    """Calcula o DRE sem efeitos colaterais"""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id or int(active_loja_id) != loja_id:
        raise HttpError(403, "Acesso negado à loja solicitada.")
    if not (1 <= mes <= 12):
        raise HttpError(400, "Mês inválido.")

    check_permission(request, loja_id)

    # Extrair info do usuario do request se der, senao default
    from django.contrib.auth.models import User
    try:
        user_id = getattr(request, 'user_id', None) or request.auth.get('user_id')
        user = User.objects.get(id=user_id)
        gerado_por = user.username
    except:
        gerado_por = "Sistema"

    # Extrair nome da loja (apenas genérico para teste sem dependencias fortes de outros models)
    loja_nome = request.auth.get('loja_nome', f"Loja {loja_id}") if isinstance(request.auth, dict) else f"Loja {loja_id}"

    from financeiro_core.app.services.dre_service import DREService
    try:
        service = DREService()
        dre_data = service.gerar(loja_id, mes, ano, loja_nome, gerado_por)
        return dre_data
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HttpError(503, "Serviço indisponível no momento.")

@router.get("/dre/{loja_id}/{mes}/{ano}/pdf")
def get_dre_pdf(request, loja_id: int, mes: int, ano: int):
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id or int(active_loja_id) != loja_id:
        raise HttpError(403, "Acesso negado à loja solicitada.")
    if not (1 <= mes <= 12):
        raise HttpError(400, "Mês inválido.")

    check_permission(request, loja_id)

    from django.contrib.auth.models import User
    try:
        user_id = getattr(request, 'user_id', None) or request.auth.get('user_id')
        user = User.objects.get(id=user_id)
        gerado_por = user.username
    except:
        gerado_por = "Sistema"

    loja_nome = request.auth.get('loja_nome', f"Loja {loja_id}") if isinstance(request.auth, dict) else f"Loja {loja_id}"

    from financeiro_core.app.services.dre_service import DREService
    from financeiro_core.reports.dre_pdf import DREPDFGenerator
    from django.http import HttpResponse
    import unicodedata

    try:
        service = DREService()
        dre_data = service.gerar(loja_id, mes, ano, loja_nome, gerado_por)

        response = HttpResponse(content_type='application/pdf')
        nome_arquivo = unicodedata.normalize('NFKD', loja_nome).encode('ASCII', 'ignore').decode('utf-8').replace(' ', '_').upper()
        response['Content-Disposition'] = f'attachment; filename="DRE_{nome_arquivo}_{mes}_{ano}.pdf"'

        gerador = DREPDFGenerator(dre_data)
        gerador.gerar(response)
        return response
    except Exception as e:
        raise HttpError(503, "Serviço indisponível no momento.")

@router.get("/dre/{loja_id}/{mes}/{ano}/xml")
def get_dre_xml(request, loja_id: int, mes: int, ano: int):
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id or int(active_loja_id) != loja_id:
        raise HttpError(403, "Acesso negado à loja solicitada.")
    if not (1 <= mes <= 12):
        raise HttpError(400, "Mês inválido.")

    check_permission(request, loja_id)

    from django.contrib.auth.models import User
    try:
        user_id = getattr(request, 'user_id', None) or request.auth.get('user_id')
        user = User.objects.get(id=user_id)
        gerado_por = user.username
    except:
        gerado_por = "Sistema"

    loja_nome = request.auth.get('loja_nome', f"Loja {loja_id}") if isinstance(request.auth, dict) else f"Loja {loja_id}"

    from financeiro_core.app.services.dre_service import DREService
    from financeiro_core.reports.dre_xml import DREXMLGenerator
    from django.http import HttpResponse
    import unicodedata

    try:
        service = DREService()
        dre_data = service.gerar(loja_id, mes, ano, loja_nome, gerado_por)

        response = HttpResponse(content_type='application/xml; charset=utf-8')
        nome_arquivo = unicodedata.normalize('NFKD', loja_nome).encode('ASCII', 'ignore').decode('utf-8').replace(' ', '_').upper()
        response['Content-Disposition'] = f'attachment; filename="DRE_{nome_arquivo}_{mes}_{ano}.xml"'

        gerador = DREXMLGenerator(dre_data)
        gerador.gerar(response)
        return response
    except Exception as e:
        raise HttpError(503, "Serviço indisponível no momento.")

class FechamentoOut(Schema):
    loja_id: int
    mes: int
    ano: int
    faturamento_bruto: Decimal
    total_dinheiro: Decimal = Decimal('0.00')
    total_cartao: Decimal = Decimal('0.00')
    total_pix: Decimal = Decimal('0.00')
    total_outros: Decimal = Decimal('0.00')
    impostos: Decimal
    receita_liquida: Decimal
    custos_produtos: Decimal
    lucro_bruto: Decimal
    despesas_operacionais: Decimal
    resultado_operacional: Decimal
    despesas_financeiras: Decimal
    lucro_liquido: Decimal
    status: str


class FechamentoPersistidoOut(Schema):
    loja_id: int
    mes: int
    ano: int
    faturamento_bruto: Decimal
    total_dinheiro: Optional[Decimal] = None
    total_cartao: Optional[Decimal] = None
    total_pix: Optional[Decimal] = None
    total_outros: Optional[Decimal] = None
    impostos: Optional[Decimal] = None
    receita_liquida: Decimal
    custos_produtos: Optional[Decimal] = None
    lucro_bruto: Optional[Decimal] = None
    despesas_operacionais: Decimal
    resultado_operacional: Decimal
    despesas_financeiras: Optional[Decimal] = None
    lucro_liquido: Optional[Decimal] = None
    status: str


@router.get(
    "/fechamento/{loja_id}/{mes}/{ano}",
    response=FechamentoPersistidoOut,
)
def obter_fechamento_persistido(request, loja_id: int, mes: int, ano: int):
    """Retorna exclusivamente o estado congelado já persistido do fechamento."""
    check_permission(request, loja_id)
    if not (1 <= mes <= 12):
        raise HttpError(400, "Mês inválido.")

    fechamento = get_object_or_404(
        FechamentoMensal,
        loja_id_externo=loja_id,
        mes=mes,
        ano=ano,
    )
    snapshot = fechamento.dados_auditoria_snapshot
    resumo = snapshot.get('resumo', {}) if isinstance(snapshot, dict) else {}
    if not isinstance(resumo, dict):
        resumo = {}

    return {
        "loja_id": fechamento.loja_id_externo,
        "mes": fechamento.mes,
        "ano": fechamento.ano,
        "faturamento_bruto": fechamento.faturamento_bruto,
        "total_dinheiro": resumo.get('total_dinheiro'),
        "total_cartao": resumo.get('total_cartao'),
        "total_pix": resumo.get('total_pix'),
        "total_outros": resumo.get('total_outros'),
        "impostos": resumo.get('impostos'),
        "receita_liquida": fechamento.receita_liquida,
        "custos_produtos": resumo.get('custos_produtos'),
        "lucro_bruto": resumo.get('lucro_bruto'),
        "despesas_operacionais": fechamento.total_despesas,
        "resultado_operacional": fechamento.resultado_operacional,
        "despesas_financeiras": resumo.get('despesas_financeiras_total'),
        "lucro_liquido": resumo.get('lucro_liquido'),
        "status": fechamento.status,
    }

@router.post("/fechamento/calcular/{loja_id}/{mes}/{ano}", response=FechamentoOut)
def calcular_fechamento(request, loja_id: int, mes: int, ano: int):
    """Calcula e persiste o fechamento mensal, chamando DREService."""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id or int(active_loja_id) != loja_id:
        raise HttpError(403, "Acesso negado à loja solicitada.")
    if not (1 <= mes <= 12):
        raise HttpError(400, "Mês inválido.")

    check_permission(request, loja_id)

    fechamento_existente = FechamentoMensal.objects.filter(
        loja_id_externo=loja_id, mes=mes, ano=ano
    ).only('status').first()
    if fechamento_existente and fechamento_existente.status == 'CONCLUIDO':
        raise HttpError(409, "Período concluído não pode ser recalculado.")

    from financeiro_core.app.services.dre_service import DREService
    try:
        service = DREService()
        loja_nome = request.auth.get('loja_nome', f"Loja {loja_id}") if isinstance(request.auth, dict) else f"Loja {loja_id}"
        gerado_por = "Sistema"
        dre_data = service.gerar(loja_id, mes, ano, loja_nome, gerado_por)
        resumo = dre_data['resumo']

        with transaction.atomic():
            fechamento = FechamentoMensal.objects.select_for_update().filter(
                loja_id_externo=loja_id, mes=mes, ano=ano
            ).first()
            if fechamento and fechamento.status == 'CONCLUIDO':
                raise HttpError(409, "Período concluído não pode ser recalculado.")
            if not fechamento:
                fechamento = FechamentoMensal(
                    loja_id_externo=loja_id, mes=mes, ano=ano, status='ABERTO'
                )

            fechamento.faturamento_bruto = resumo['receita_bruta']
            fechamento.total_taxas = resumo['taxas_cartao']
            fechamento.receita_liquida = resumo['receita_liquida']
            fechamento.total_despesas = resumo['despesas_operacionais']
            fechamento.resultado_operacional = resumo['resultado_operacional']
            fechamento.dados_auditoria_snapshot = json.loads(
                json.dumps(dre_data, cls=DjangoJSONEncoder)
            )
            fechamento.save()

        return {
            "loja_id": fechamento.loja_id_externo,
            "mes": fechamento.mes,
            "ano": fechamento.ano,
            "faturamento_bruto": fechamento.faturamento_bruto,
            "total_dinheiro": resumo['total_dinheiro'],
            "total_cartao": resumo['total_cartao'],
            "total_pix": resumo['total_pix'],
            "total_outros": resumo['total_outros'],
            "impostos": resumo['impostos'],
            "receita_liquida": fechamento.receita_liquida,
            "custos_produtos": resumo['custos_produtos'],
            "lucro_bruto": resumo['lucro_bruto'],
            "despesas_operacionais": fechamento.total_despesas,
            "resultado_operacional": fechamento.resultado_operacional,
            "despesas_financeiras": resumo['despesas_financeiras_total'],
            "lucro_liquido": resumo['lucro_liquido'],
            "status": fechamento.status,
        }
    except HttpError:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HttpError(503, "Serviço indisponível no momento.")
