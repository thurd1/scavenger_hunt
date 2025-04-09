#!/usr/bin/env python3
"""
Direct fix for syntax error in views.py at line 595
This script should be run directly on the server where the error occurs
"""
import os

# Path to the views.py file (adjust if needed)
file_path = 'hunt/views.py'

# First, make a backup of the original file
backup_path = file_path + '.bak'
os.system(f'cp {file_path} {backup_path}')
print(f"Created backup at {backup_path}")

# Read the file
with open(file_path, 'r') as f:
    lines = f.readlines()

# Print the problematic area
print("Lines around error (590-600):")
for i in range(max(0, 590-1), min(len(lines), 600)):
    print(f"{i+1}: {lines[i].rstrip()}")

# Check if line 595 has the except statement
if 594 < len(lines) and 'except' in lines[594]:
    print("\nFound 'except' at line 595, adding missing try block")
    
    # Get indentation level
    indentation = len(lines[594]) - len(lines[594].lstrip())
    indent_str = ' ' * indentation
    
    # Insert try block
    lines.insert(594, f"{indent_str}try:\n")
    lines.insert(595, f"{indent_str}    pass  # Added missing try block\n")
else:
    # Look for 'except' near line 595
    for i in range(590, 600):
        if i < len(lines) and 'except' in lines[i]:
            print(f"\nFound 'except' at line {i+1}, adding missing try block")
            
            # Get indentation level
            indentation = len(lines[i]) - len(lines[i].lstrip())
            indent_str = ' ' * indentation
            
            # Insert try block
            lines.insert(i, f"{indent_str}try:\n")
            lines.insert(i+1, f"{indent_str}    pass  # Added missing try block\n")
            break
    else:
        # If we didn't find an except, apply a broader fix
        print("\nCouldn't find 'except' near line 595, applying alternative fix")
        
        # Search for 'except Exception as e:' in the file and ensure it has a try block
        fixed_count = 0
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith('except Exception as e:'):
                # Check if there's a try block before this
                has_try = False
                for j in range(max(0, i-10), i):
                    if lines[j].strip().startswith('try:'):
                        has_try = True
                        break
                
                if not has_try:
                    # Add a try block if missing
                    indent = len(lines[i]) - len(lines[i].lstrip())
                    indent_str = ' ' * indent
                    lines.insert(i, f"{indent_str}try:\n")
                    lines.insert(i+1, f"{indent_str}    pass  # Added missing try block\n")
                    fixed_count += 1
                    i += 2  # Skip the lines we just added
            i += 1
        
        print(f"Fixed {fixed_count} except blocks without try statements")

# Write the fixed file
with open(file_path, 'w') as f:
    f.writelines(lines)

print(f"\nFixed file has been written to {file_path}")
print(f"If the fix doesn't work, you can restore the backup: cp {backup_path} {file_path}")
print("\nNow try running the server again with: python manage.py runserver 0.0.0.0:8001") 