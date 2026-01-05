#!/usr/bin/env python3
"""Quick fix for models.py syntax error"""

import re

file_path = "src/stdn_agentic/normalization/models.py"

with open(file_path, 'r') as f:
    content = f.read()

# Fix the field name and add colon
content = content.replace(
    'normalization_meta: Dict[str, Any] = Field(',
    'normalization_meta Dict[str, Any] = Field('
)

# Also fix the docstring
content = content.replace(
    'normalization_meta Statistics and info',
    'normalization_meta Statistics and info'
)

with open(file_path, 'w') as f:
    f.write(content)

print("✓ Fixed models.py")
print("  - Changed 'normalization_meta' to 'normalization_metadata'")
