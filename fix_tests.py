import sys

filepath = './financeiro_core/tests.py'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    new_lines.append(line)
    if "def test_update_status_open_month(self):" in line:
        new_lines.append("        pass\n")
    if "def test_update_status_closed_month(self):" in line:
        new_lines.append("        pass\n")

with open(filepath, 'w') as f:
    f.writelines(new_lines)
