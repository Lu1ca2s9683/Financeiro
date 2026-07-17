from ninja import Router, Schema, Field
from financeiro_core.app.services.dre_repositories import DjangoRepositorioTaxas, DjangoRepositorioDespesas

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


class ContaBancariaOut(Schema):
    id: int
    nome: str
    tipo: str
    banco_codigo: str
    agencia: str
    conta: str
    saldo_atual: Decimal
    ativo: bool

class ContaBancariaIn(Schema):
    nome: str
    tipo: str
    banco_codigo: str = ''
    agencia: str = ''
    conta: str = ''
    saldo_inicial: Decimal = Decimal('0.00')

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
    loja_id_externo: int
    mes: int
    ano: int
    receita_bruta: Decimal
    total_dinheiro: Decimal = Decimal('0.00')
    total_cartao: Decimal = Decimal('0.00')
    total_pix: Decimal = Decimal('0.00')
    impostos: Decimal
    receita_liquida: Decimal
    custos_produtos: Decimal
    lucro_bruto: Decimal
    despesas_operacionais: Decimal
    resultado_operacional: Decimal
    despesas_financeiras: Decimal
    lucro_liquido: Decimal

@router.post("/fechamento/calcular/{loja_id}/{mes}/{ano}", response=FechamentoOut)
class FechamentoOut(Schema):
    loja_id_externo: int
    mes: int
    ano: int
    receita_bruta: Decimal
    total_dinheiro: Decimal = Decimal('0.00')
    total_cartao: Decimal = Decimal('0.00')
    total_pix: Decimal = Decimal('0.00')
    impostos: Decimal
    receita_liquida: Decimal
    custos_produtos: Decimal
    lucro_bruto: Decimal
    despesas_operacionais: Decimal
    resultado_operacional: Decimal
    despesas_financeiras: Decimal
    lucro_liquido: Decimal

@router.post("/fechamento/calcular/{loja_id}/{mes}/{ano}", response=FechamentoOut)
def calcular_fechamento(request, loja_id: int, mes: int, ano: int):
    """Calcula e persiste o fechamento mensal, chamando DREService."""
    active_loja_id = request.auth.get('active_loja_id') if isinstance(request.auth, dict) else getattr(request, 'active_loja_id', None)
    if not active_loja_id or int(active_loja_id) != loja_id:
        raise HttpError(403, "Acesso negado à loja solicitada.")
    if not (1 <= mes <= 12):
        raise HttpError(400, "Mês inválido.")

    check_permission(request, loja_id)

    from financeiro_core.app.services.dre_service import DREService
    try:
        service = DREService()
        loja_nome = request.auth.get('loja_nome', f"Loja {loja_id}") if isinstance(request.auth, dict) else f"Loja {loja_id}"
        gerado_por = "Sistema"
        dre_data = service.gerar(loja_id, mes, ano, loja_nome, gerado_por)
        resumo = dre_data['resumo']

        with transaction.atomic():
            fechamento = FechamentoMensal.objects.filter(loja_id_externo=loja_id, mes=mes, ano=ano).first()
            if not fechamento:
                fechamento = FechamentoMensal(
                    loja_id_externo=loja_id, mes=mes, ano=ano, status='ABERTO'
                )

            fechamento.faturamento_bruto = resumo['receita_bruta']
            fechamento.total_taxas = resumo['taxas_cartao']
            fechamento.receita_liquida = resumo['receita_liquida']
            fechamento.total_despesas = resumo['despesas_operacionais']
            fechamento.resultado_operacional = resumo['resultado_operacional']
            fechamento.dados_auditoria_snapshot = dre_data
            fechamento.save()

        return {
            "loja_id_externo": fechamento.loja_id_externo,
            "mes": fechamento.mes,
            "ano": fechamento.ano,
            "receita_bruta": fechamento.faturamento_bruto,
            "total_dinheiro": Decimal('0.00'),
            "total_cartao": Decimal('0.00'),
            "total_pix": Decimal('0.00'),
            "impostos": resumo['impostos'],
            "receita_liquida": fechamento.receita_liquida,
            "custos_produtos": resumo['custos_produtos'],
            "lucro_bruto": resumo['lucro_bruto'],
            "despesas_operacionais": fechamento.total_despesas,
            "resultado_operacional": fechamento.resultado_operacional,
            "despesas_financeiras": resumo['despesas_financeiras_total'],
            "lucro_liquido": resumo['lucro_liquido']
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HttpError(503, "Serviço indisponível no momento.")
