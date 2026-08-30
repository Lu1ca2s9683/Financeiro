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
from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.db import IntegrityError, transaction
from django.core.serializers.json import DjangoJSONEncoder
from django.core import signing
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
from financeiro_core.infrastructure.vendas_client import VendasClientSQL

OFX_IMPORT_TOKEN_SALT = "financeiro.ofx.import.v1"

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
    fitid: Optional[str] = None
    fingerprint: str
    trntype: Optional[str] = None
    checknum: Optional[str] = None
    refnum: Optional[str] = None
    name: Optional[str] = None
    memo: Optional[str] = None
    categoria_sugerida_id: Optional[int] = None
    ja_importada: bool = False
    duplicate_reason: Optional[str] = None
    ofx_import_token: Optional[str] = None


@router.post(
    "/extrato/importar-despesas/{loja_id}/",
    response=List[ExtratoItemOut],
    auth=AuthBearer(),
)
def importar_extrato_despesas(
    request,
    loja_id: int,
    conta_origem_id: int,
    file: File[UploadedFile],
):
    """Lê um OFX/OFC sem persistir lançamentos e respeita a loja autenticada."""
    check_permission(request, loja_id)
    conta = ContaBancaria.objects.filter(
        id=conta_origem_id,
        loja_id_externo=loja_id,
        ativo=True,
    ).first()
    if conta is None:
        raise HttpError(400, "Conta bancária ativa inválida para a loja atual.")

    raw_content = file.read()
    try:
        file_content = raw_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        file_content = raw_content.decode("latin-1")

    from financeiro_core.app.services.ofx_parser import OfxParserService

    transactions = OfxParserService.parse(file_content)
    if not transactions:
        raise HttpError(400, "Arquivo OFX/OFC inválido ou sem transações válidas.")

    fitids = {
        item["fitid"]
        for item in transactions
        if item["tipo"] == "SAIDA" and item.get("fitid")
    }
    fingerprints = {
        item["fingerprint"]
        for item in transactions
        if item["tipo"] == "SAIDA" and item.get("fingerprint")
    }
    fitids_importados = set(
        ContaPagar.objects.filter(
            conta_origem=conta,
            ofx_fitid__in=fitids,
        ).values_list("ofx_fitid", flat=True)
    )
    fingerprints_importados = set(
        ContaPagar.objects.filter(
            conta_origem=conta,
            ofx_fingerprint__in=fingerprints,
        ).values_list("ofx_fingerprint", flat=True)
    )

    for item in transactions:
        item["categoria_sugerida_id"] = (
            OfxParserService.adivinhar_categoria(item["descricao_original"], loja_id)
            if item["tipo"] == "SAIDA"
            else None
        )
        item["ja_importada"] = False
        item["duplicate_reason"] = None
        item["ofx_import_token"] = None
        if item["tipo"] == "SAIDA":
            item["ofx_import_token"] = _assinar_importacao_ofx(
                loja_id,
                conta.id,
                item,
            )
            if item.get("fitid") in fitids_importados:
                item["ja_importada"] = True
                item["duplicate_reason"] = "FITID"
            elif item.get("fingerprint") in fingerprints_importados:
                item["ja_importada"] = True
                item["duplicate_reason"] = "FINGERPRINT"

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


class VendedorAtivoOut(Schema):
    id: int
    nome: str
    loja_id: int


@router.get(
    "/vendedores/ativos/{loja_id}",
    response=List[VendedorAtivoOut],
    auth=AuthBearer(),
)
def listar_vendedores_ativos(request, loja_id: int):
    """Expõe somente a identidade pública de vendedores ativos da loja."""
    check_permission(request, loja_id)
    try:
        return VendasClientSQL().get_vendedores_ativos_por_loja(loja_id)
    except Exception as exc:
        raise HttpError(
            503,
            "Sistema de Vendas indisponível para consultar vendedores ativos.",
        ) from exc

# --- DESPESAS (CRUD) ---

class RateioIn(Schema):
    id: Optional[int] = None
    descricao: str
    valor: Decimal
    categoria_id: Optional[int] = None
    vendedor_id_externo: Optional[int] = None

class DespesaIn(Schema):
    descricao: str
    loja_id: Optional[int] = None
    categoria_id: int
    valor: Decimal
    data_competencia: date
    data_transacao: date
    rateios: List[RateioIn] = []
    fornecedor_id: Optional[int] = None
    conta_origem_id: Optional[int] = None
    origem_lancamento: str = "MANUAL"
    ofx_fitid: Optional[str] = None
    ofx_fingerprint: Optional[str] = None
    descricao_original_extrato: Optional[str] = None
    ofx_import_token: Optional[str] = None
    vendedor_id_externo: Optional[int] = None

class RateioOut(Schema):
    id: int
    descricao: str
    valor: Decimal
    categoria_id: Optional[int]
    vendedor_id_externo: Optional[int] = None
    vendedor_nome_snapshot: Optional[str] = None

class DespesaOut(Schema):
    id: int
    descricao: str
    valor_liquido: Decimal
    data_transacao: Optional[date] = None
    data_competencia: date
    categoria: CategoriaOut = None
    conta_origem_id: Optional[int] = None
    origem_lancamento: str
    ofx_fitid: Optional[str] = None
    ofx_fingerprint: Optional[str] = None
    descricao_original_extrato: Optional[str] = None
    vendedor_id_externo: Optional[int] = None
    vendedor_nome_snapshot: Optional[str] = None

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


def _valor_centavos(valor: Decimal) -> Decimal:
    return Decimal(str(valor)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _assinar_importacao_ofx(loja_id: int, conta_origem_id: int, item: dict) -> str:
    return signing.dumps(
        {
            "loja_id": loja_id,
            "conta_origem_id": conta_origem_id,
            "fitid": (item.get("fitid") or "").strip() or None,
            "fingerprint": item["fingerprint"],
            "data_transacao": item["data_transacao"].isoformat(),
            "valor": f"{_valor_centavos(item['valor']):.2f}",
            "descricao_original_extrato": item["descricao_original"],
            "tipo": "SAIDA",
        },
        salt=OFX_IMPORT_TOKEN_SALT,
    )


def _validar_token_importacao_ofx(
    payload: DespesaIn,
    loja_id: int,
    conta_origem_id: int,
    fitid: Optional[str],
    fingerprint: str,
    descricao_original: str,
):
    if not payload.ofx_import_token:
        raise HttpError(400, "Token assinado de importação OFX é obrigatório.")

    try:
        dados_assinados = signing.loads(
            payload.ofx_import_token,
            salt=OFX_IMPORT_TOKEN_SALT,
        )
    except (signing.BadSignature, TypeError, ValueError) as exc:
        raise HttpError(400, "Token OFX inválido ou adulterado.") from exc

    esperado = {
        "loja_id": loja_id,
        "conta_origem_id": conta_origem_id,
        "fitid": fitid,
        "fingerprint": fingerprint,
        "data_transacao": payload.data_transacao.isoformat(),
        "valor": f"{_valor_centavos(payload.valor):.2f}",
        "descricao_original_extrato": descricao_original,
        "tipo": "SAIDA",
    }
    if not isinstance(dados_assinados, dict) or any(
        dados_assinados.get(campo) != valor
        for campo, valor in esperado.items()
    ):
        raise HttpError(
            400,
            "Token OFX incompatível com os dados bancários enviados.",
        )


def _obter_conta_ativa_da_loja(conta_id: Optional[int], loja_id: int):
    if conta_id is None:
        return None
    conta = ContaBancaria.objects.filter(
        id=conta_id,
        loja_id_externo=loja_id,
        ativo=True,
    ).first()
    if conta is None:
        raise HttpError(400, "Conta bancária ativa inválida para a loja atual.")
    return conta


def _preparar_origem_lancamento(payload: DespesaIn, loja_id: int):
    origem = (payload.origem_lancamento or 'MANUAL').upper().strip()
    if origem not in {'MANUAL', 'OFX'}:
        raise HttpError(400, "Origem do lançamento inválida.")

    conta = _obter_conta_ativa_da_loja(payload.conta_origem_id, loja_id)
    fitid = (payload.ofx_fitid or '').strip() or None
    fingerprint = (payload.ofx_fingerprint or '').strip() or None
    descricao_original = payload.descricao_original_extrato

    if origem == 'OFX':
        if conta is None:
            raise HttpError(400, "Uma conta bancária ativa é obrigatória para OFX.")
        if fingerprint is None:
            raise HttpError(400, "Fingerprint OFX é obrigatório.")
        if not descricao_original:
            raise HttpError(400, "Descrição original do extrato é obrigatória.")
        _validar_token_importacao_ofx(
            payload,
            loja_id,
            conta.id,
            fitid,
            fingerprint,
            descricao_original,
        )
    elif fitid or fingerprint or descricao_original or payload.ofx_import_token:
        raise HttpError(400, "Metadados OFX exigem origem_lancamento=OFX.")

    return origem, conta, fitid, fingerprint, descricao_original


def _preparar_rateios_e_vendedores(
    payload: DespesaIn,
    categoria_principal: CategoriaDespesa,
    loja_id: int,
    despesa_existente: Optional[ContaPagar] = None,
    valor_liquido_alvo: Optional[Decimal] = None,
):
    if payload.vendedor_id_externo is not None and payload.rateios:
        raise HttpError(
            400,
            "O vendedor da despesa não pode ser usado junto com rateios.",
        )

    valor_bruto = _valor_centavos(payload.valor)
    valor_rateio_alvo = _valor_centavos(
        valor_liquido_alvo
        if valor_liquido_alvo is not None
        else valor_bruto
    )
    categoria_ids = {
        rateio.categoria_id
        for rateio in payload.rateios
        if rateio.categoria_id is not None
    }
    categorias = {
        categoria.id: categoria
        for categoria in CategoriaDespesa.objects.filter(id__in=categoria_ids)
    }
    if len(categorias) != len(categoria_ids):
        inexistentes = sorted(categoria_ids - set(categorias))
        raise HttpError(400, f"Categorias de rateio inexistentes: {inexistentes}.")

    splits_existentes = {}
    if despesa_existente is not None:
        splits_existentes = {
            split.id: split for split in despesa_existente.splits.all()
        }

    preparados = []
    total_rateado = Decimal('0.00')
    vendedor_ids_para_consulta = set()

    for rateio in payload.rateios:
        valor = _valor_centavos(rateio.valor)
        if valor <= 0:
            raise HttpError(400, "Cada valor de rateio deve ser maior que zero.")
        total_rateado += valor
        categoria = categorias.get(rateio.categoria_id, categoria_principal)
        snapshot_preservado = None
        split_existente = splits_existentes.get(rateio.id)
        if (
            split_existente is not None
            and rateio.vendedor_id_externo is not None
            and split_existente.vendedor_id_externo == rateio.vendedor_id_externo
            and split_existente.vendedor_nome_snapshot
        ):
            snapshot_preservado = split_existente.vendedor_nome_snapshot

        if rateio.vendedor_id_externo is not None:
            if categoria.grupo_contabil != 'PESSOAL':
                raise HttpError(
                    400,
                    "Vendedor só pode ser associado a categoria do grupo PESSOAL.",
                )
            if snapshot_preservado is None:
                vendedor_ids_para_consulta.add(rateio.vendedor_id_externo)

        preparados.append({
            "payload": rateio,
            "valor": valor,
            "categoria": categoria,
            "snapshot_preservado": snapshot_preservado,
        })

    if payload.rateios:
        saldo = valor_rateio_alvo - total_rateado
        if saldo != Decimal('0.00'):
            raise HttpError(
                400,
                f"Saldo a ratear deve ser R$ 0,00. Saldo atual: {saldo:.2f}.",
            )

    snapshot_parent = None
    if payload.vendedor_id_externo is not None:
        if categoria_principal.grupo_contabil != 'PESSOAL':
            raise HttpError(
                400,
                "Vendedor só pode ser associado a categoria do grupo PESSOAL.",
            )
        if (
            despesa_existente is not None
            and despesa_existente.vendedor_id_externo == payload.vendedor_id_externo
            and despesa_existente.vendedor_nome_snapshot
        ):
            snapshot_parent = despesa_existente.vendedor_nome_snapshot
        else:
            vendedor_ids_para_consulta.add(payload.vendedor_id_externo)

    vendedores = {}
    if vendedor_ids_para_consulta:
        try:
            vendedores_ativos = VendasClientSQL().get_vendedores_ativos_por_loja(
                loja_id
            )
        except Exception as exc:
            raise HttpError(
                503,
                "Sistema de Vendas indisponível para validar vendedor.",
            ) from exc
        vendedores = {
            int(vendedor["id"]): vendedor
            for vendedor in vendedores_ativos
            if int(vendedor["loja_id"]) == loja_id
        }
        ausentes = sorted(vendedor_ids_para_consulta - set(vendedores))
        if ausentes:
            raise HttpError(
                400,
                f"Vendedor ativo não encontrado para a loja atual: {ausentes}.",
            )

    if payload.vendedor_id_externo is not None and snapshot_parent is None:
        snapshot_parent = vendedores[payload.vendedor_id_externo]["nome"]

    for preparado in preparados:
        rateio = preparado["payload"]
        if (
            rateio.vendedor_id_externo is not None
            and preparado["snapshot_preservado"] is None
        ):
            preparado["snapshot_preservado"] = vendedores[
                rateio.vendedor_id_externo
            ]["nome"]

    return valor_bruto, snapshot_parent, preparados


def _garantir_fatos_ofx_imutaveis(despesa: ContaPagar, payload: DespesaIn):
    if despesa.origem_lancamento != 'OFX':
        return

    if (
        _valor_centavos(payload.valor) != _valor_centavos(despesa.valor_bruto)
        or payload.data_transacao != despesa.data_transacao
    ):
        raise HttpError(
            400,
            "Valor e data da transação são fatos bancários de um OFX e não podem ser editados.",
        )

    campos_enviados = getattr(
        payload,
        "model_fields_set",
        getattr(payload, "__fields_set__", set()),
    )
    valores_bancarios = {
        "conta_origem_id": despesa.conta_origem_id,
        "origem_lancamento": despesa.origem_lancamento,
        "ofx_fitid": despesa.ofx_fitid,
        "ofx_fingerprint": despesa.ofx_fingerprint,
        "descricao_original_extrato": despesa.descricao_original_extrato,
    }
    for campo, valor_persistido in valores_bancarios.items():
        if campo not in campos_enviados:
            continue
        valor_enviado = getattr(payload, campo)
        if campo == "ofx_fitid":
            valor_enviado = (valor_enviado or "").strip() or None
        if valor_enviado != valor_persistido:
            raise HttpError(
                400,
                "Os fatos bancários de uma transação OFX não podem ser editados.",
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
    origem, conta, fitid, fingerprint, descricao_original = (
        _preparar_origem_lancamento(payload, loja_id_do_token)
    )
    valor_despesa, vendedor_nome, rateios_preparados = (
        _preparar_rateios_e_vendedores(
            payload,
            categoria,
            loja_id_do_token,
        )
    )

    try:
        with transaction.atomic():
            despesa = ContaPagar.objects.create(
                descricao=payload.descricao,
                loja_id_externo=loja_id_do_token,
                categoria=categoria,
                fornecedor=fornecedor,
                valor_bruto=valor_despesa,
                data_competencia=payload.data_competencia,
                data_transacao=payload.data_transacao,
                conta_origem=conta,
                origem_lancamento=origem,
                ofx_fitid=fitid,
                ofx_fingerprint=fingerprint,
                descricao_original_extrato=descricao_original,
                vendedor_id_externo=payload.vendedor_id_externo,
                vendedor_nome_snapshot=vendedor_nome,
                criado_por_id=getattr(request, 'user_id', None),
            )
            for preparado in rateios_preparados:
                rateio = preparado["payload"]
                RateioDespesa.objects.create(
                    despesa=despesa,
                    descricao=rateio.descricao,
                    valor=preparado["valor"],
                    categoria=preparado["categoria"],
                    vendedor_id_externo=rateio.vendedor_id_externo,
                    vendedor_nome_snapshot=preparado["snapshot_preservado"],
                )
    except IntegrityError as exc:
        if origem == 'OFX':
            raise HttpError(
                409,
                "Esta transação OFX já existe para a conta selecionada.",
            ) from exc
        raise
    return despesa

@router.put("/despesas/{despesa_id}", response=DespesaOut)
def editar_despesa(request, despesa_id: int, payload: DespesaIn):
    """Atualiza uma despesa e recalcula valores."""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id:
        raise HttpError(400, "Nenhuma loja ativa no contexto")

    despesa = get_object_or_404(ContaPagar, id=despesa_id, loja_id_externo=active_loja_id)

    _garantir_periodo_caixa_aberto(active_loja_id, despesa.data_transacao)
    _garantir_fatos_ofx_imutaveis(despesa, payload)
    if (
        despesa.origem_lancamento != 'OFX'
        and payload.data_transacao != despesa.data_transacao
    ):
        _garantir_periodo_caixa_aberto(active_loja_id, payload.data_transacao)

    if not CategoriaDespesa.objects.filter(id=payload.categoria_id).exists():
        raise HttpError(404, f"Categoria {payload.categoria_id} não encontrada.")
    categoria = CategoriaDespesa.objects.get(id=payload.categoria_id)

    fornecedor = None
    if payload.fornecedor_id:
        fornecedor = get_object_or_404(Fornecedor, id=payload.fornecedor_id)

    valor_liquido_prospectivo = _valor_centavos(
        _valor_centavos(payload.valor)
        - _valor_centavos(despesa.valor_desconto)
        + _valor_centavos(despesa.valor_acrescimo)
    )
    valor_despesa, vendedor_nome, rateios_preparados = (
        _preparar_rateios_e_vendedores(
            payload,
            categoria,
            active_loja_id,
            despesa_existente=despesa,
            valor_liquido_alvo=valor_liquido_prospectivo,
        )
    )
    conta = despesa.conta_origem
    if despesa.origem_lancamento != 'OFX':
        conta = _obter_conta_ativa_da_loja(
            payload.conta_origem_id,
            active_loja_id,
        )

    with transaction.atomic():
        despesa.descricao = payload.descricao
        despesa.categoria = categoria
        despesa.fornecedor = fornecedor
        despesa.valor_bruto = valor_despesa
        despesa.data_competencia = payload.data_competencia
        despesa.data_transacao = payload.data_transacao
        despesa.conta_origem = conta
        despesa.vendedor_id_externo = payload.vendedor_id_externo
        despesa.vendedor_nome_snapshot = vendedor_nome
        despesa.save()

        despesa.splits.all().delete()
        for preparado in rateios_preparados:
            rateio = preparado["payload"]
            RateioDespesa.objects.create(
                despesa=despesa,
                descricao=rateio.descricao,
                valor=preparado["valor"],
                categoria=preparado["categoria"],
                vendedor_id_externo=rateio.vendedor_id_externo,
                vendedor_nome_snapshot=preparado["snapshot_preservado"],
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
