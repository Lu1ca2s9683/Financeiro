import re
from datetime import datetime
from decimal import Decimal

file_content = """
<STMTTRN>
<GENTRN>
<TRNTYPE>1
<DTPOSTED>20260629
<TRNAMT>-80.00
<FITID>
<CHKNUM>
<MEMO>PIX ENVIADO LUCAS ANTONIO TOMAZ 365.358.418-39
</GENTRN>
</STMTTRN>
"""

transactions = []
stmtrs_blocks = re.split(r'<STMTTRN>', file_content, flags=re.IGNORECASE)

print(f"Found {len(stmtrs_blocks)} blocks")

for block in stmtrs_blocks[1:]:
    print("--- BLOCK ---")
    print(block)

    dt_match = re.search(r'<DTPOSTED>(\d{8})', block, flags=re.IGNORECASE)
    if not dt_match:
        print("NO DTPOSTED MATCH")
        continue
    print(f"DTPOSTED: {dt_match.group(1)}")

    amt_match = re.search(r'<TRNAMT>([-\d\.]+)', block, flags=re.IGNORECASE)
    if not amt_match:
        print("NO TRNAMT MATCH")
        continue
    print(f"TRNAMT: {amt_match.group(1)}")

    desc_match = re.search(r'<MEMO>(.*?)(?:\r?\n|<|$)', block, flags=re.IGNORECASE)
    if not desc_match:
        print("NO MEMO MATCH")
        continue
    print(f"MEMO: {desc_match.group(1).strip()}")

    transactions.append("OK")

print(f"Parsed {len(transactions)} transactions")
