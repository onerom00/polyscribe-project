import importlib, traceback
mods = ["app.routes.auth"]
for m in mods:
    try:
        mod = importlib.import_module(m)
        print("OK ", m, "has bp:", hasattr(mod,"bp"))
        if hasattr(mod,"bp"):
            bp = getattr(mod,"bp")
            print("   bp.name:", getattr(bp,"name",None), " url_prefix:", getattr(bp,"url_prefix",None))
    except Exception as e:
        print("ERR", m, "=>", repr(e))
        traceback.print_exc()
