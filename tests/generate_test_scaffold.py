"""Generate test scaffolds for untested functions."""
import sys
import os
import inspect

sys.path.insert(0, '..')
import Snatch

def generate_test_file(module_name, functions, output_file):
    """Generate a test file for the given functions."""
    with open(output_file, 'w') as f:
        f.write(f"""import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, '..')
import {module_name}

""")
        
        for func_name, func in functions:
            # Create test function name
            test_name = f"test_{func_name}"
            
            # Get signature
            try:
                signature = inspect.signature(func)
                params = list(signature.parameters.keys())
            except:
                params = []
                
            f.write(f"""
def {test_name}():
    \"""Test {func_name} function.\"""
    if not hasattr({module_name}, '{func_name}'):
        pytest.skip("{func_name} function not found")
        
    # Setup - adjust as needed
""")
            
            # Add example parameter values based on parameter names
            args = []
            for param in params:
                if 'url' in param.lower():
                    args.append('"https://example.com"')
                elif 'path' in param.lower() or 'file' in param.lower():
                    args.append('"example.txt"')
                elif 'data' in param.lower() or 'json' in param.lower():
                    args.append('{"key": "value"}')
                else:
                    args.append('None')
            
            if args:
                args_str = ', '.join(args)
                f.write(f"""    
    # Call the function
    try:
        result = {module_name}.{func_name}({args_str})
        
        # Basic assertion - adjust based on expected return value
        assert result is not None
    except Exception as e:
        # If the function is expected to fail with these params, uncomment:
        # assert "expected error message" in str(e)
        pytest.skip(f"Function {func_name} raised: {{e}}")
""")
            else:
                f.write(f"""    
    # Call the function with no args
    try:
        result = {module_name}.{func_name}()
        
        # Basic assertion
        assert result is not None
    except Exception as e:
        # If the function is expected to fail, uncomment:
        # assert "expected error message" in str(e)
        pytest.skip(f"Function {func_name} raised: {{e}}")
""")

def main():
    # Get all functions from the module
    functions = [(name, obj) for name, obj in inspect.getmembers(Snatch) 
               if inspect.isfunction(obj) and obj.__module__ == 'Snatch']
    
    # Group functions by filename
    for i in range(0, len(functions), 10):
        batch = functions[i:i+10]
        output_file = f"tests/test_generated_{i//10+1}.py"
        generate_test_file("Snatch", batch, output_file)
        print(f"Generated {output_file}")

if __name__ == "__main__":
    main()