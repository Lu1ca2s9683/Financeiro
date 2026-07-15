import sys

filepath = './financeiro-frontend/src/services/api.ts'
with open(filepath, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "importExtrato: async (file: File): Promise<ExtratoItem[]> => {" in line:
        new_lines.append(line)
    elif "const activeLojaId = localStorage.getItem('active_loja_id');" in line and "importExtrato" in ''.join(new_lines[-10:]):
        new_lines.append(line)
    else:
        new_lines.append(line)

# Let's just append the new method to the api object
# We need to find the end of the api object...
# But we can just add a new api call. It's safer to just do the fetch inline in the component to avoid messing up the API client structure if we don't know it well. Or we can just use fetch inline.
