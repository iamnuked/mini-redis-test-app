import importlib.util
import sys
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI_MAIN_PATH = PROJECT_ROOT / "cmd" / "mini_redis_cli" / "main.py"


def load_cli_main_module() -> ModuleType:
    module_name = "mini_redis_cli_main_for_tests"
    if module_name in sys.modules:
        return sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, CLI_MAIN_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load CLI module from {CLI_MAIN_PATH}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
