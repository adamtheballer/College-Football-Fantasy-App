import importlib
import sys

api_app = importlib.import_module("api.app")
sys.modules[__name__ + ".app"] = api_app
