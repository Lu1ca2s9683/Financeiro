import sys
import re

filepath = './financeiro_core/app/services/ofx_parser.py'
with open(filepath, 'r') as f:
    content = f.read()

# Replace the bad regex
# desc_match = re.search(r'<(MEMO)>(.*?)(?:<|$)', block, flags=re.IGNORECASE)
# desc = desc_match.group(2).strip() if desc_match else "Sem descrição"
old_regex = r"desc_match = re.search(r'<(MEMO)>(.*?)(?:<|$)', block, flags=re.IGNORECASE)"
new_regex = r"desc_match = re.search(r'<MEMO>(.*?)(?:\r?\n|<|$)', block, flags=re.IGNORECASE)"

content = content.replace(old_regex, new_regex)

# Fix the group index
old_group = r"desc = desc_match.group(2).strip() if desc_match else \"Sem descrição\""
new_group = r"desc = desc_match.group(1).strip() if desc_match else \"Sem descrição\""

content = content.replace(old_group, new_group)

with open(filepath, 'w') as f:
    f.write(content)

print("Regex updated")
