"""Script to discover and document functions in Snatch.py."""
import sys
import os
import inspect

sys.path.insert(0, '..')
import Snatch

def discover_functions():
    """Print all functions and classes in the Snatch module."""
    functions = []
    classes = []
    
    for name, obj in inspect.getmembers(Snatch):
        if inspect.isfunction(obj):
            functions.append((name, obj))
        elif inspect.isclass(obj):
            classes.append((name, obj))
    
    print("=== FUNCTIONS ===")
    for name, func in functions:
        print(f"{name}: {inspect.getmodule(func).__name__}.{name}")
        try:
            signature = str(inspect.signature(func))
            print(f"  Signature: {signature}")
            if func.__doc__:
                print(f"  Docstring: {func.__doc__.strip()}")
            source_file = inspect.getsourcefile(func)
            source_lines, line_num = inspect.getsourcelines(func)
            print(f"  Source: {source_file}, lines {line_num}-{line_num + len(source_lines) - 1}")
        except:
            print("  (Could not retrieve signature or source)")
        print()
    
    print("=== CLASSES ===")
    for name, cls in classes:
        print(f"{name}: {inspect.getmodule(cls).__name__}.{name}")
        if cls.__doc__:
            print(f"  Docstring: {cls.__doc__.strip()}")
        try:
            source_file = inspect.getsourcefile(cls)
            source_lines, line_num = inspect.getsourcelines(cls)
            print(f"  Source: {source_file}, lines {line_num}-{line_num + len(source_lines) - 1}")
        except:
            print("  (Could not retrieve source)")
        print()

if __name__ == "__main__":
    discover_functions()