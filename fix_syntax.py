"""
Fix syntax error in views.py around line 595
"""
import re

# Read the file
with open('scavenger_hunt/hunt/views.py', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

# Extract lines around the error for analysis
print("Examining the area around line 595:")
for i in range(max(0, 585), min(len(lines), 605)):
    print(f"{i+1}: {lines[i]}")

# Check for incomplete try-except structure
try_line = None
for i in range(594, 550, -1):
    if lines[i].strip().startswith('try:'):
        try_line = i
        print(f"\nFound try statement at line {i+1}: {lines[i]}")
        break

# Fix the specific issue - manually insert any missing code
# The issue is likely an incorrectly formatted try-except block

# Option 1: Add a matching try block if missing
if not try_line:
    indent = len(lines[594]) - len(lines[594].lstrip())
    lines.insert(594, ' ' * indent + 'try:')
    lines.insert(595, ' ' * (indent + 4) + 'pass  # Added missing try block')
    print("\nInserted a missing try block before line 595")

# Option 2: Fix indentation of the try-except block
else:
    # Check if there's any code between try and except
    has_code_between = False
    for i in range(try_line + 1, 594):
        if lines[i].strip() and not lines[i].strip().startswith('#'):
            has_code_between = True
            break
    
    if not has_code_between:
        # Add a pass statement if there's no code between try and except
        indent = len(lines[try_line]) - len(lines[try_line].lstrip()) + 4
        lines.insert(try_line + 1, ' ' * indent + 'pass  # Added missing code in try block')
        print("\nAdded a pass statement in empty try block")

# Option 3: Fix the entire function containing the issue
# Find function containing line 595
function_start = None
for i in range(594, 400, -1):
    if re.match(r'\s*def\s+', lines[i]):
        function_start = i
        print(f"\nFound function start at line {i+1}: {lines[i]}")
        break

if function_start:
    # Extract the function to analyze its structure
    print("\nFull function containing the error:")
    function_end = 1000  # Default large value
    for i in range(function_start + 1, min(len(lines), function_start + 200)):
        if re.match(r'\s*def\s+', lines[i]):
            function_end = i - 1
            break
    
    for i in range(function_start, min(function_end + 1, len(lines))):
        print(f"{i+1}: {lines[i]}")

# Specific fix for line 595 - examine code and manually fix the issue
line_594 = lines[594] if 594 < len(lines) else ""
line_595 = lines[595] if 595 < len(lines) else ""
line_596 = lines[596] if 596 < len(lines) else ""

print(f"\nLines directly around the error:")
print(f"594: {line_594}")
print(f"595: {line_595}")
print(f"596: {line_596}")

# Get context: Check what's around the function to understand the structure
print("\nBroader context:")
for i in range(max(0, 570), min(len(lines), 620)):
    print(f"{i+1}: {lines[i]}")

# Apply specific fix based on the observed issue
# For this specific issue, modify these lines to fix it directly
fixed_content = content

# First fix: Try adding a proper try statement before except if needed
fixed_content = re.sub(
    r'(\n\s+)except Exception as e:',
    r'\1try:\n\1    pass  # Added missing try block\n\1except Exception as e:',
    fixed_content
)

# Second fix: If it's a block indentation issue, adjust the except's indentation
fixed_content = re.sub(
    r'(\n)(\s+)except Exception as e:',
    r'\1\2try:\n\2    pass  # Added missing try block\n\2except Exception as e:',
    fixed_content
)

# Third fix: Check if there's a misplaced parenthesis or bracket before the except
fixed_content = re.sub(
    r'(\)\s*\n\s*)except Exception as e:',
    r')\n        try:\n            pass  # Added missing try block\n        except Exception as e:',
    fixed_content
)

# Write the fixed content to a new file
with open('scavenger_hunt/hunt/views.py.fixed', 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print("\nApplied multiple potential fixes to scavenger_hunt/hunt/views.py.fixed")
print("Examine the output above to understand the issue and confirm the fix works")
print("To apply the fix: mv scavenger_hunt/hunt/views.py.fixed scavenger_hunt/hunt/views.py") 