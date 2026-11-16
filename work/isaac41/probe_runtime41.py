import sys, importlib, json

result = {"python": sys.version, "executable": sys.executable, "modules": {}}
for name in ["numpy", "torch", "scipy", "pip", "isaacsim", "omni.isaac.kit"]:
    try:
        m = importlib.import_module(name)
        result["modules"][name] = {
            "version": getattr(m, "__version__", None),
            "file": str(getattr(m, "__file__", None)),
        }
    except Exception as e:
        result["modules"][name] = {"error": str(e)}
print(json.dumps(result, indent=2))
