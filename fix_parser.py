import sys

filepath = './financeiro_core/app/services/ofx_parser.py'
with open(filepath, 'r') as f:
    content = f.read()

old_desc = "desc_match = re.search(r'<(MEMO|NAME)>(.*?)(?:</\\1>|<|$)', block, flags=re.IGNORECASE)"
new_desc = "desc_match = re.search(r'<(MEMO)>(.*?)(?:<|$)', block, flags=re.IGNORECASE)"

content = content.replace(old_desc, new_desc)

with open(filepath, 'w') as f:
    f.write(content)

print("OFC/OFX Parser updated")
