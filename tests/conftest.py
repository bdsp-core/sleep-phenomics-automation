"""Load focused viewer modules without importing optional ML backends."""
import importlib.util
import sys
import types
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load_source_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def pytest_configure():
    # app.viewer eagerly imports every optional phenotype backend. Parser tests
    # deliberately isolate the ingestion boundary instead.
    load_source_module("spa_xdf_parser", "app/viewer/xdf_parser.py")
