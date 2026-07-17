import xml.etree.ElementTree as ET
from decimal import Decimal
from django.http import HttpResponse

class DREXMLGenerator:
    def __init__(self, dre_data):
        self.dre = dre_data

    def gerar(self, response: HttpResponse):
        root = ET.Element("dre", versao="1.0", regime="CAIXA")

        # A. Identificação
        ident_data = self.dre.get("identificacao", {})
        ident = ET.SubElement(root, "identificacao")
        ET.SubElement(ident, "sistema").text = "Sistema Financeiro"
        loja = ET.SubElement(ident, "loja", id=str(ident_data.get("loja_id", "")))
        loja.text = ident_data.get("loja_nome", "")
        periodo = ET.SubElement(ident, "periodo")
        ET.SubElement(periodo, "mes").text = str(ident_data.get("mes", ""))
        ET.SubElement(periodo, "ano").text = str(ident_data.get("ano", ""))
        ET.SubElement(periodo, "descricao").text = ident_data.get("periodo_descricao", "")
        ET.SubElement(ident, "gerado_em").text = ident_data.get("gerado_em", "")
        ET.SubElement(ident, "gerado_por").text = ident_data.get("gerado_por", "")

        # B. Resumo
        resumo_data = self.dre.get("resumo", {})
        resumo = ET.SubElement(root, "resumo")
        for k, v in resumo_data.items():
            val_str = f"{float(v):.2f}"
            ET.SubElement(resumo, k).text = val_str

        # C. Linhas
        linhas_data = self.dre.get("linhas", [])
        linhas = ET.SubElement(root, "linhas")
        for l_data in linhas_data:
            linha = ET.SubElement(linhas, "linha",
                codigo=str(l_data.get("codigo", "")),
                tipo=l_data.get("tipo", ""),
                nivel=str(l_data.get("nivel", 0)),
                ordem=str(l_data.get("ordem", 0))
            )
            ET.SubElement(linha, "descricao").text = l_data.get("descricao", "")
            ET.SubElement(linha, "valor").text = f"{float(l_data.get('valor', 0)):.2f}"
            ET.SubElement(linha, "percentual_receita").text = f"{float(l_data.get('percentual_receita', 0)):.2f}"

        # D. Grupos Detalhados
        grupos_data = self.dre.get("grupos_detalhados", [])
        grupos = ET.SubElement(root, "grupos_detalhados")
        for g_data in grupos_data:
            grupo = ET.SubElement(grupos, "grupo", codigo=g_data.get("grupo_contabil", ""))
            ET.SubElement(grupo, "descricao").text = g_data.get("descricao", "")
            ET.SubElement(grupo, "total").text = f"{float(g_data.get('total', 0)):.2f}"

            categorias = ET.SubElement(grupo, "categorias")
            for c_data in g_data.get("categorias", []):
                categoria = ET.SubElement(categorias, "categoria", id=str(c_data.get("categoria_id", "")))
                ET.SubElement(categoria, "nome").text = c_data.get("categoria_nome", "")
                ET.SubElement(categoria, "total").text = f"{float(c_data.get('total', 0)):.2f}"

                lancamentos = ET.SubElement(categoria, "lancamentos")
                for lanc_data in c_data.get("lancamentos", []):
                    rateio_id = lanc_data.get("rateio_id")
                    if rateio_id:
                        lancamento = ET.SubElement(lancamentos, "lancamento",
                            despesa_id=str(lanc_data.get("despesa_id", "")),
                            rateio_id=str(rateio_id),
                            tipo_origem=lanc_data.get("tipo_origem", "")
                        )
                    else:
                        lancamento = ET.SubElement(lancamentos, "lancamento",
                            despesa_id=str(lanc_data.get("despesa_id", "")),
                            tipo_origem=lanc_data.get("tipo_origem", "")
                        )
                    ET.SubElement(lancamento, "data_transacao").text = lanc_data.get("data_transacao", "")
                    ET.SubElement(lancamento, "descricao").text = lanc_data.get("descricao", "")
                    fornec = lanc_data.get("fornecedor_nome")
                    ET.SubElement(lancamento, "fornecedor").text = fornec if fornec else ""
                    ET.SubElement(lancamento, "valor").text = f"{float(lanc_data.get('valor', 0)):.2f}"

        # E. Qualidade Dados
        qual_data = self.dre.get("qualidade_dados", {})
        qual = ET.SubElement(root, "qualidade_dados")
        for k, v in qual_data.items():
            if isinstance(v, Decimal):
                val_str = f"{float(v):.2f}"
            elif isinstance(v, bool):
                val_str = "true" if v else "false"
            else:
                val_str = str(v)
            ET.SubElement(qual, k).text = val_str

        # Indent and write
        ET.indent(root, space="    ", level=0)
        xml_str = ET.tostring(root, encoding="utf-8", method="xml", xml_declaration=True)
        response.write(xml_str)
