import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

class OfxParserService:
    @staticmethod
    def _extrair_campo(block: str, campo: str) -> str | None:
        match = re.search(
            rf'<{campo}>\s*([^<\r\n]*)',
            block,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        valor = match.group(1).strip()
        return valor or None

    @staticmethod
    def _normalizar_texto(valor: str | None) -> str:
        return ' '.join((valor or '').upper().split())

    @staticmethod
    def parse(file_content: str) -> list[dict]:
        """
        Parses OFX/OFC file content and returns a list of transactions.
        Each transaction has: data_transacao, descricao_original, valor, tipo (ENTRADA/SAIDA)
        """
        transactions = []
        ocorrencias: dict[str, int] = {}

        stmtrs_blocks = re.split(r'<STMTTRN>', file_content, flags=re.IGNORECASE)

        for block in stmtrs_blocks[1:]:
            try:
                # Find date (DTPOSTED)
                dt_match = re.search(r'<DTPOSTED>\s*(\d{8})', block, flags=re.IGNORECASE)
                if not dt_match:
                    continue
                date_str = dt_match.group(1)
                dt = datetime.strptime(date_str, "%Y%m%d").date()

                # Find amount (TRNAMT)
                amt_match = re.search(r'<TRNAMT>\s*([-\d\.]+)', block, flags=re.IGNORECASE)
                if not amt_match:
                    continue
                amt = Decimal(amt_match.group(1)).quantize(
                    Decimal('0.01'),
                    rounding=ROUND_HALF_UP,
                )

                trntype = OfxParserService._extrair_campo(block, 'TRNTYPE')
                fitid = OfxParserService._extrair_campo(block, 'FITID')
                checknum = OfxParserService._extrair_campo(block, 'CHECKNUM')
                refnum = OfxParserService._extrair_campo(block, 'REFNUM')
                name = OfxParserService._extrair_campo(block, 'NAME')
                memo = OfxParserService._extrair_campo(block, 'MEMO')
                desc = memo or name or "Sem descrição"

                if fitid:
                    representacao_identidade = (
                        f"FITID|{OfxParserService._normalizar_texto(fitid)}"
                    )
                else:
                    assinatura_base = '|'.join([
                        dt.isoformat(),
                        format(amt, 'f'),
                        OfxParserService._normalizar_texto(trntype),
                        OfxParserService._normalizar_texto(name),
                        OfxParserService._normalizar_texto(memo),
                        OfxParserService._normalizar_texto(checknum),
                        OfxParserService._normalizar_texto(refnum),
                    ])
                    ocorrencias[assinatura_base] = (
                        ocorrencias.get(assinatura_base, 0) + 1
                    )
                    representacao_identidade = (
                        f"{assinatura_base}#{ocorrencias[assinatura_base]}"
                    )

                fingerprint = hashlib.sha256(
                    representacao_identidade.encode('utf-8')
                ).hexdigest()

                tipo = "SAIDA" if amt < 0 else "ENTRADA"

                transactions.append(
                    {
                        "data_transacao": dt,
                        "descricao_original": desc,
                        "valor": abs(amt),
                        "tipo": tipo,
                        "fitid": fitid,
                        "fingerprint": fingerprint,
                        "trntype": trntype,
                        "checknum": checknum,
                        "refnum": refnum,
                        "name": name,
                        "memo": memo,
                    }
                )

            except (InvalidOperation, ValueError):
                continue

        return transactions

    @staticmethod
    def adivinhar_categoria(descricao_original: str, loja_id: int) -> int | None:
        """
        Searches recent ContaPagar entries for similar descriptions to guess the category.
        """
        from financeiro_core.models import ContaPagar

        words = [w for w in descricao_original.split() if len(w) > 3]

        for word in words:
            recent_expenses = ContaPagar.objects.filter(loja_id_externo=loja_id, descricao__icontains=word).order_by('-id')[:10]
            if recent_expenses.exists():
                return recent_expenses.first().categoria_id

        return None
