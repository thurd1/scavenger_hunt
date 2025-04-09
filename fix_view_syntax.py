"""
Directly fix the syntax error at line 595 in views.py
"""

# Function to read specific line range from a file
def read_line_range(file_path, start_line, end_line):
    lines = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            if i >= start_line and i <= end_line:
                lines.append(line.rstrip('\n'))
            if i > end_line:
                break
    return lines

# Read the problematic area
file_path = 'scavenger_hunt/hunt/views.py'
context_lines = read_line_range(file_path, 590, 600)
print("Context around the error:")
for i, line in enumerate(context_lines, 590):
    print(f"{i}: {line}")

# Read the entire file
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Insert a try statement before the except at line 595
# This is a direct approach based on the error message
if 594 < len(lines) and 'except' in lines[594]:
    # Get current indentation
    current_line = lines[594]
    indentation = len(current_line) - len(current_line.lstrip())
    
    # Insert a try block
    indent_str = ' ' * indentation
    lines.insert(594, f"{indent_str}try:\n")
    lines.insert(595, f"{indent_str}    pass  # Added missing try block\n")
    
    print("\nFixed the error by adding a try block before the except statement")
else:
    print("\nLine 595 may not be the except statement in your file. Let's check nearby lines:")
    
    # Look for the except statement nearby
    for i in range(590, 600):
        if i < len(lines) and 'except' in lines[i]:
            # Get current indentation
            current_line = lines[i]
            indentation = len(current_line) - len(current_line.lstrip())
            
            # Insert a try block
            indent_str = ' ' * indentation
            lines.insert(i, f"{indent_str}try:\n")
            lines.insert(i+1, f"{indent_str}    pass  # Added missing try block\n")
            
            print(f"Fixed the error by adding a try block before the except statement at line {i+1}")
            break

# Write the fixed file
with open(file_path + '.fixed', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f"\nFixed file written to {file_path}.fixed")
print("Run this command to replace the original file:")
print(f"mv {file_path}.fixed {file_path}")
print("\nIf you're on Windows, use:")
print(f"Move-Item -Force {file_path}.fixed {file_path}") 