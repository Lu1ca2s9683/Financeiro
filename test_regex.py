import re

block = """
<GENTRN>
<TRNTYPE>1
<DTPOSTED>20260629
<TRNAMT>-80.00
<FITID>
<CHKNUM>
<MEMO>PIX ENVIADO LUCAS ANTONIO TOMAZ 365.358.418-39
</GENTRN>
"""

# The current regex:
desc_match = re.search(r'<(MEMO)>(.*?)(?:<|$)', block, flags=re.IGNORECASE)
if desc_match:
    print(f"MATCHED: '{desc_match.group(2).strip()}'")
else:
    print("NO MATCH")

# Test a better regex for multiline if needed
desc_match2 = re.search(r'<MEMO>(.*?)(?:\r?\n|<|$)', block, flags=re.IGNORECASE)
if desc_match2:
    print(f"BETTER MATCH: '{desc_match2.group(1).strip()}'")
else:
    print("NO BETTER MATCH")
