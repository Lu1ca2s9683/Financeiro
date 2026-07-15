from datetime import datetime
from decimal import Decimal
import re

class OfxParserService:
    @staticmethod
    def parse(file_content: str) -> list[dict]:
        """
        Parses OFX/OFC file content and returns a list of transactions.
        Each transaction has: data_transacao, descricao_original, valor, tipo (ENTRADA/SAIDA)
        """
        transactions = []

        stmtrs_blocks = re.split(r'<STMTTRN>', file_content, flags=re.IGNORECASE)

        for block in stmtrs_blocks[1:]:
            try:
                # Find date (DTPOSTED)
                dt_match = re.search(r'<DTPOSTED>(\d{8})', block, flags=re.IGNORECASE)
                if not dt_match:
                    continue
                date_str = dt_match.group(1)
                dt = datetime.strptime(date_str, "%Y%m%d").date()

                # Find amount (TRNAMT)
                amt_match = re.search(r'<TRNAMT>([-\d\.]+)', block, flags=re.IGNORECASE)
                if not amt_match:
                    continue
                amt = Decimal(amt_match.group(1))

                # Find description (MEMO or NAME)
                desc_match = re.search(r'<MEMO>(.*?)(?:\r?\n|<|$)', block, flags=re.IGNORECASE)
                desc = desc_match.group(2).strip() if desc_match else "Sem descrição"

                tipo = "SAIDA" if amt < 0 else "ENTRADA"

                transactions.append({
                    "data_transacao": dt,
                    "descricao_original": desc,
                    "valor": abs(amt),
                    "tipo": tipo
                })

            except Exception as e:
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
