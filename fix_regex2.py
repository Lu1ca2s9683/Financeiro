import sys

filepath = './financeiro_core/app/services/ofx_parser.py'
with open(filepath, 'r') as f:
    content = f.read()

# I see the problem:
# desc = desc_match.group(2).strip() if desc_match else "Sem descrição"
# Wait! In the previous step I used `group(1)` in the `test_full_parser.py`, but my regex update script missed it or it wasn't correct.
# Wait, let's look at `financeiro_core/app/services/ofx_parser.py` again.
# It has: `desc = desc_match.group(2).strip() if desc_match else "Sem descrição"`
# BUT the regex `r'<MEMO>(.*?)(?:\r?\n|<|$)'` only has ONE group now.
# This causes an IndexError inside the try-except, which silently `continue`s, resulting in an empty array!

# Let's fix this!

old_group = r"desc = desc_match.group(2).strip() if desc_match else \"Sem descrição\""
new_group = r"desc = desc_match.group(1).strip() if desc_match else \"Sem descrição\""

content = content.replace(old_group, new_group)

with open(filepath, 'w') as f:
    f.write(content)

print("Group index updated")
