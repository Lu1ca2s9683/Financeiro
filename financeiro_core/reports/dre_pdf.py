import io
from decimal import Decimal

from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

class DREPDFGenerator:
    def __init__(self, dre_data):
        self.dre = dre_data
        self.identificacao = self.dre.get("identificacao", {})
        self.resumo = self.dre.get("resumo", {})
        self.linhas = self.dre.get("linhas", [])
        self.grupos = self.dre.get("grupos_detalhados", [])
        self.qualidade = self.dre.get("qualidade_dados", {})
        self.composicao_recebimentos = self.dre.get(
            "composicao_recebimentos", {}
        )
        self.qualidade_recebimentos = self.dre.get(
            "qualidade_recebimentos", {}
        )
        self.pessoal_por_vendedor = self.dre.get("pessoal_por_vendedor", {})
        self.styles = getSampleStyleSheet()

    def gerar(self, response: HttpResponse):
        doc = SimpleDocTemplate(response, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []

        # Estilos Customizados
        title_style = ParagraphStyle(name="TitleStyle", parent=self.styles['Heading1'], fontSize=16, spaceAfter=6, textColor=colors.HexColor("#1e293b"))
        subtitle_style = ParagraphStyle(name="SubTitleStyle", parent=self.styles['Normal'], fontSize=10, textColor=colors.HexColor("#64748b"), spaceAfter=20)
        heading_style = ParagraphStyle(name="Heading2Style", parent=self.styles['Heading2'], fontSize=12, textColor=colors.HexColor("#1e293b"), spaceBefore=15, spaceAfter=10, keepWithNext=1)
        normal_style = self.styles['Normal']

        # A. Cabeçalho
        loja_nome = self.identificacao.get('loja_nome', 'Desconhecida')
        periodo = self.identificacao.get('periodo_descricao', '')
        gerado_por = self.identificacao.get('gerado_por', 'Sistema')
        gerado_em = self.identificacao.get('gerado_em', '')

        elements.append(Paragraph("Demonstrativo do Resultado do Exercício", title_style))
        cabecalho_txt = f"Sistema Financeiro - Loja: {loja_nome}<br/>Mês de Referência: {periodo} | Regime de CAIXA<br/>Gerado por: {gerado_por} em {gerado_em}"
        elements.append(Paragraph(cabecalho_txt, subtitle_style))

        # B. Resumo Executivo
        elements.append(Paragraph("Resumo Executivo", heading_style))

        def format_currency(val):
            if val is None: val = 0

            return f"{float(val):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        def format_perc(val):
            if val is None: val = 0

            return f"{float(val):.2f}%"

        resumo_data = [
            ["Receita Bruta", "Receita Líquida", "Lucro Bruto", "Resultado Operacional", "Resultado Líquido"],
            [
                format_currency(self.resumo.get('receita_bruta', 0)),
                format_currency(self.resumo.get('receita_liquida', 0)),
                format_currency(self.resumo.get('lucro_bruto', 0)),
                format_currency(self.resumo.get('resultado_operacional', 0)),
                format_currency(self.resumo.get('lucro_liquido', 0)),
            ],
            ["Margem", "Margem Oper.", "Margem Líquida", "", ""],
            [
                format_perc(self.resumo.get('margem_bruta_percentual', 0)),
                format_perc(self.resumo.get('margem_operacional_percentual', 0)),
                format_perc(self.resumo.get('margem_liquida_percentual', 0)),
                "",
                ""
            ]
        ]

        t_resumo = Table(resumo_data, colWidths=[100]*5)
        t_resumo.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#475569")),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BACKGROUND', (0,2), (2,2), colors.HexColor("#f1f5f9")),
            ('FONTNAME', (0,2), (2,2), 'Helvetica-Bold'),
        ]))
        elements.append(t_resumo)
        elements.append(Spacer(1, 20))

        if self.composicao_recebimentos:
            elements.append(Paragraph("Composição dos Recebimentos", heading_style))
            recebimentos_data = [["Grupo", "Detalhamento", "Valor"]]
            linhas_totais = []

            def adicionar_grupo(nome, dados, detalhes):
                linhas_totais.append(len(recebimentos_data))
                recebimentos_data.append([
                    nome,
                    "Total",
                    format_currency(dados.get("total", 0)),
                ])
                for chave, descricao in detalhes:
                    valor = dados.get(chave, 0)
                    if valor and Decimal(str(valor)) != Decimal('0.00'):
                        recebimentos_data.append([
                            "",
                            descricao,
                            format_currency(valor),
                        ])

            adicionar_grupo(
                "Dinheiro",
                self.composicao_recebimentos.get("dinheiro", {}),
                [],
            )
            adicionar_grupo(
                "Pix",
                self.composicao_recebimentos.get("pix", {}),
                [
                    ("conta", "Pix em Conta"),
                    ("maquina", "Pix via Maquininha"),
                    ("nao_detalhado", "Pix sem detalhamento"),
                ],
            )
            adicionar_grupo(
                "Cartão",
                self.composicao_recebimentos.get("cartao", {}),
                [
                    ("debito", "Débito"),
                    ("credito_avista", "Crédito à vista"),
                    ("credito_parcelado", "Crédito parcelado"),
                    (
                        "credito_nao_identificado",
                        "Crédito - parcelamento não informado",
                    ),
                    ("nao_identificado", "Cartão sem identificação"),
                ],
            )
            adicionar_grupo(
                "Outros",
                self.composicao_recebimentos.get("outros", {}),
                [
                    ("voucher", "Voucher"),
                    ("nao_identificado", "Outros"),
                ],
            )

            t_recebimentos = Table(
                recebimentos_data,
                colWidths=[100, 330, 100],
                repeatRows=1,
            )
            recebimentos_style = TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('ALIGN', (2,0), (2,-1), 'RIGHT'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('LINEBELOW', (0,0), (-1,-1), 0.25, colors.lightgrey),
            ])
            for indice in linhas_totais:
                recebimentos_style.add(
                    'BACKGROUND',
                    (0, indice),
                    (-1, indice),
                    colors.HexColor("#f1f5f9"),
                )
                recebimentos_style.add(
                    'FONTNAME', (0, indice), (-1, indice), 'Helvetica-Bold'
                )
            t_recebimentos.setStyle(recebimentos_style)
            elements.append(t_recebimentos)
            elements.append(Spacer(1, 10))

        if self.qualidade_recebimentos:
            avisos_recebimentos = []
            q_receb = self.qualidade_recebimentos
            if q_receb.get("possui_credito_sem_detalhe"):
                avisos_recebimentos.append(
                    "Crédito com detalhamento indisponível: "
                    f"R$ {format_currency(q_receb.get('valor_credito_sem_detalhe'))} "
                    "não possui informação de parcelamento. Nenhuma taxa específica "
                    "de crédito foi estimada para esse valor."
                )
            if q_receb.get("possui_cartao_sem_subtipo"):
                avisos_recebimentos.append(
                    "Cartão sem identificação de modalidade: "
                    f"R$ {format_currency(q_receb.get('valor_cartao_sem_subtipo'))}. "
                    "Nenhuma taxa foi estimada para esse valor."
                )
            if q_receb.get("possui_pagamentos_elegiveis_sem_taxa"):
                avisos_recebimentos.append(
                    "Taxa não configurada: "
                    f"R$ {format_currency(q_receb.get('valor_pagamentos_sem_taxa_configurada'))} "
                    "em pagamentos de modalidade conhecida não encontrou taxa "
                    "aplicável. O Resultado Líquido pode estar superestimado."
                )
            if not q_receb.get("receita_conservada", True):
                avisos_recebimentos.append(
                    "A composição dos recebimentos não conserva a Receita Bruta. "
                    "O período requer revisão dos dados de origem."
                )

            if avisos_recebimentos:
                elements.append(Paragraph(
                    "Qualidade / Limitações dos Recebimentos",
                    heading_style,
                ))
                for aviso in avisos_recebimentos:
                    elements.append(Paragraph(
                        aviso,
                        ParagraphStyle(
                            name="PaymentWarningStyle",
                            parent=self.styles['Normal'],
                            fontSize=8,
                            textColor=colors.HexColor("#92400e"),
                            spaceAfter=5,
                        ),
                    ))
                elements.append(Spacer(1, 10))

        # C. DRE Cascata
        elements.append(Paragraph("Demonstrativo Detalhado", heading_style))
        dre_data = [["Código", "Descrição", "Valor", "% Receita"]]

        for linha in self.linhas:
            codigo = str(linha.get("codigo", ""))
            descricao = linha.get("descricao", "")
            valor = float(linha.get("valor", 0))
            perc = float(linha.get("percentual_receita", 0))

            valor_str = format_currency(valor)
            if linha.get("tipo") == "SUBTRACAO":
                valor_str = f"({valor_str})"
            perc_str = format_perc(perc)

            dre_data.append([codigo, descricao, valor_str, perc_str])

        t_dre = Table(dre_data, colWidths=[40, 320, 100, 70], repeatRows=1)

        dre_style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('ALIGN', (0,0), (1,-1), 'LEFT'),
            ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.lightgrey),
        ])

        # Aplicar Negrito em Totais
        for i, linha in enumerate(self.linhas):
            if linha.get("tipo") == "TOTAL":
                dre_style.add('FONTNAME', (0, i+1), (-1, i+1), 'Helvetica-Bold')
            if linha.get("nivel") == 1:
                dre_style.add('LEFTPADDING', (1, i+1), (1, i+1), 15)

        # Destaque final (Lucro Liquido)
        dre_style.add('BACKGROUND', (0, len(dre_data)-1), (-1, len(dre_data)-1), colors.HexColor("#f8fafc"))
        dre_style.add('FONTNAME', (0, len(dre_data)-1), (-1, len(dre_data)-1), 'Helvetica-Bold')

        t_dre.setStyle(dre_style)
        elements.append(t_dre)
        elements.append(Spacer(1, 20))

        if Decimal(str(self.pessoal_por_vendedor.get("total_pessoal", 0))) > 0:
            elements.append(Paragraph(
                "Despesas com Pessoal por Vendedor",
                heading_style,
            ))
            pessoal_data = [["Vendedor", "Valor"]]
            for vendedor in self.pessoal_por_vendedor.get("vendedores", []):
                pessoal_data.append([
                    vendedor.get("vendedor_nome", ""),
                    format_currency(vendedor.get("valor", 0)),
                ])
            nao_individualizado = self.pessoal_por_vendedor.get(
                "total_nao_individualizado",
                0,
            )
            if Decimal(str(nao_individualizado)) != Decimal('0.00'):
                pessoal_data.append([
                    "Não individualizado",
                    format_currency(nao_individualizado),
                ])
            pessoal_data.append([
                "Total Pessoal",
                format_currency(
                    self.pessoal_por_vendedor.get("total_pessoal", 0)
                ),
            ])
            t_pessoal = Table(pessoal_data, colWidths=[430, 100], repeatRows=1)
            t_pessoal.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor("#f1f5f9")),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ]))
            elements.append(t_pessoal)
            elements.append(Spacer(1, 20))

        # D. Análise de Despesas
        elements.append(Paragraph("Análise Analítica das Despesas", heading_style))

        for grupo in self.grupos:
            elements.append(Paragraph(f"Grupo: {grupo.get('descricao')} - Total: {format_currency(grupo.get('total'))}", ParagraphStyle(name="GroupStyle", parent=self.styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor("#334155"), spaceBefore=10, spaceAfter=5)))

            for cat in grupo.get('categorias', []):
                elements.append(Paragraph(f"Categoria: {cat.get('categoria_nome')} - Total: {format_currency(cat.get('total'))}", ParagraphStyle(name="CatStyle", parent=self.styles['Normal'], fontSize=9, textColor=colors.HexColor("#475569"), spaceAfter=5)))

                lanc_data = [["Data", "Descrição", "Origem/Fornecedor", "ID Despesa", "Valor"]]
                for lanc in cat.get('lancamentos', []):
                    desc = lanc.get("descricao", "")[:40] # truncate
                    origem = lanc.get("tipo_origem", "")
                    fornec = lanc.get("fornecedor_nome")
                    if fornec:
                        origem += f" ({fornec[:15]})"
                    vendedor_nome = lanc.get("vendedor_nome")
                    if vendedor_nome:
                        origem += f" - {vendedor_nome[:20]}"

                    lanc_data.append([
                        lanc.get("data_transacao", ""),
                        desc,
                        origem,
                        str(lanc.get("despesa_id", "")),
                        format_currency(lanc.get("valor", 0))
                    ])

                if len(lanc_data) > 1:
                    t_lanc = Table(lanc_data, colWidths=[60, 220, 140, 50, 60])
                    t_lanc.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
                        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#64748b")),
                        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                        ('ALIGN', (4,0), (4,-1), 'RIGHT'),
                        ('FONTSIZE', (0,0), (-1,-1), 7),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                        ('TOPPADDING', (0,0), (-1,-1), 3),
                        ('LINEBELOW', (0,0), (-1,-1), 0.25, colors.lightgrey),
                    ]))
                    elements.append(t_lanc)
                    elements.append(Spacer(1, 10))

        # E. Qualidade de Dados
        elements.append(Paragraph("Qualidade dos Dados do Período", heading_style))
        q = self.qualidade
        q_txt = f"""Despesas processadas: {q.get('quantidade_despesas_consideradas')} (Valor: {format_currency(q.get('valor_total_despesas_consideradas'))})<br/>
Despesas s/ rateio: {q.get('quantidade_despesas_sem_rateio')}<br/>
Despesas c/ rateio válido: {q.get('quantidade_despesas_com_rateio_valido')}<br/>
Despesas c/ rateio inválido: {q.get('quantidade_despesas_com_rateio_invalido')}"""
        elements.append(Paragraph(q_txt, ParagraphStyle(name="QStyle", parent=self.styles['Normal'], fontSize=8)))

        if q.get('possui_rateios_invalidos'):
            elements.append(Spacer(1, 5))
            aviso = "ATENÇÃO: Existem despesas cujo total rateado não corresponde ao valor da despesa. Esses registros foram considerados pela categoria principal e necessitam de revisão."
            elements.append(Paragraph(aviso, ParagraphStyle(name="WarningStyle", parent=self.styles['Normal'], fontSize=8, textColor=colors.red)))

        # Geração do PDF
        def rodape(canvas, doc):
            canvas.saveState()
            canvas.setFont('Helvetica', 7)
            canvas.setFillColor(colors.gray)
            canvas.drawString(30, 20, "Documento gerado automaticamente pelo Sistema Financeiro - Regime de Caixa")
            canvas.drawRightString(A4[0] - 30, 20, f"Página {doc.page}")
            canvas.restoreState()

        doc.build(elements, onFirstPage=rodape, onLaterPages=rodape)
