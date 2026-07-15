import sys

filepath = './financeiro-frontend/src/components/FloatingNav.tsx'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "const menuItems = [" in line:
        new_lines.append(line)
    elif "{ icon: Settings, label: 'Conferência', href: '/relatorios/conferencia' }," in line:
        new_lines.append(line)
        new_lines.append("    { icon: Settings, label: 'Configurações', href: '/configuracoes' },\n")
    else:
        new_lines.append(line)

with open(filepath, 'w') as f:
    f.writelines(new_lines)

print("Floating nav updated to include Configurações")
