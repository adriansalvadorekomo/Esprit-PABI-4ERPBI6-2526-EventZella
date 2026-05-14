import sys
sys.path.insert(0, 'backend')

try:
    from eventzilla_api.app import create_app
    app = create_app()
    print("OK: App created")
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            print(f"  {','.join(route.methods or [])} {route.path}")
    paths = [r.path for r in app.routes if hasattr(r, 'path')]
    for r in ['/categories', '/predict/fidelisation', '/health']:
        print(f"  {r}: {'FOUND' if r in paths else 'MISSING'}")
except Exception as e:
    import traceback
    traceback.print_exc()
