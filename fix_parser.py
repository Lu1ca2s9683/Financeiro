import sys
filepath = './financeiro_core/app/services/ofx_parser.py'
with open(filepath, 'r') as f:
    content = f.read()

# Make it extremely resilient to spacing
content = content.replace(r"<DTPOSTED>(\d{8})", r"<DTPOSTED>\s*(\d{8})")
content = content.replace(r"<TRNAMT>([-\d\.]+)", r"<TRNAMT>\s*([-\d\.]+)")
content = content.replace(r"<MEMO>(.*?)(?:\r?\n|<|$)", r"<MEMO>\s*(.*?)(?:\r?\n|<|$)")

with open(filepath, 'w') as f:
    f.write(content)
