# sandbox/validator.py
import ast

ALLOWED_IMPORTS = {
    # Data analysis and visualization
    "pandas",
    "numpy",
    "plotly",
    # Standard library – safe and commonly used
    "json",
    "re",
    "math",
    "collections",
    "datetime",
    "typing",
    "itertools",
    "random",
    "statistics",
    "string",
    "functools",
    # Datalyze internal utilities (allowed)
    "utils",
}

BLOCKED_IMPORTS = {
    "os",
    "subprocess",
    "socket",
    "sys",
}

BLOCKED_FUNCTIONS = {
    "eval",
    "exec",
    "__import__",
}


def validate_code_ast(code: str) -> tuple[bool, str]:
    """
    Statically inspects generated code before execution using Python's AST parser.
    Blocks forbidden imports and unsafe execution functions.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, f"Syntax error: {e}"

    for node in ast.walk(tree):
        # Handle standard imports: "import pandas as pd"
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".")[0]
                if module in BLOCKED_IMPORTS:
                    return False, f"Blocked import: {module}"
                if module not in ALLOWED_IMPORTS:
                    return False, f"Import not allowed: {module}"

        # Handle from-imports: "from subprocess import Popen"
        elif isinstance(node, ast.ImportFrom):
            module = node.module.split(".")[0] if node.module else ""
            if module in BLOCKED_IMPORTS:
                return False, f"Blocked import: {module}"
            if module not in ALLOWED_IMPORTS:
                return False, f"Import not allowed: {module}"

        # Handle unsafe core functions and __import__ bypass tricks
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_FUNCTIONS:
                return False, f"Blocked function: {node.func.id}"

    return True, ""