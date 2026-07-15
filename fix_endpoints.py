import sys
import re

filepath = './financeiro_core/app/api/endpoints.py'
with open(filepath, 'r') as f:
    content = f.read()

# Remove the broken staticmethods
content = re.sub(r'    @staticmethod\n\n    @staticmethod\n\n    @staticmethod\n        # Se o status já é ATRASADO ou se venceu e não está pago\n        if obj\.status == \'ATRASADO\':\n            return True\n        return obj\.data_vencimento < date\.today\(\)\n', '', content)
content = re.sub(r'    @staticmethod\n\n    @staticmethod\n\n    @staticmethod\n', '', content)

with open(filepath, 'w') as f:
    f.write(content)
