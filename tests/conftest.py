"""Import the integration's pure-Python modules without pulling in Home Assistant.

The package __init__ imports homeassistant; tests only need model/client, so we
register a bare namespace package that skips __init__.py.
"""
import pathlib
import sys
import types

PKG_DIR = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "mittog"
pkg = types.ModuleType("mittog")
pkg.__path__ = [str(PKG_DIR)]
sys.modules.setdefault("mittog", pkg)
