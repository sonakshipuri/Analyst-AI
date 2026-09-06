# sandbox/executor.py
import subprocess
import sys
import tempfile
import os

_UNICODE_DASHES = {
    '\u2011': '-',
    '\u2013': '-',
    '\u2014': '-',
}

def _clean_dashes(text: str) -> str:
    """Replace problematic dash characters with regular hyphen."""
    for old, new in _UNICODE_DASHES.items():
        text = text.replace(old, new)
    return text

def run_code(code: str, timeout: int = 30) -> dict:
    """
    Execute Python code in a subprocess with forced UTF-8 encoding.

    Returns:
        dict: {'success': bool, 'output': str, 'error': str}
    """
    code = _clean_dashes(code)

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        encoding="utf-8"
    ) as f:
        f.write(code)
        tmp_path = f.name

    try:
        # Set UTF-8 environment for subprocess
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'

        # Get the project root (parent directory of sandbox)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Add project_root to PYTHONPATH so the subprocess can find 'utils', 'orchestrator', etc.
        pythonpath = env.get('PYTHONPATH', '')
        if pythonpath:
            env['PYTHONPATH'] = f"{project_root}{os.pathsep}{pythonpath}"
        else:
            env['PYTHONPATH'] = project_root
 
        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env
        )

        return {
            "success": result.returncode == 0,
            "output": _clean_dashes(result.stdout),
            "error": _clean_dashes(result.stderr),
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"Code execution timed out after {timeout}s",
        }

    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": str(e),
        }

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)