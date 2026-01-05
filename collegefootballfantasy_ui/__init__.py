import importlib
import sys

ui_app = importlib.import_module("ui.app")
sys.modules[__name__ + ".app"] = ui_app
