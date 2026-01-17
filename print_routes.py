from run_auth_wrapper import app
print("== URL MAP ==")
for r in sorted(app.url_map.iter_rules(), key=lambda x: x.rule):
    methods = ",".join(sorted(m for m in r.methods if m not in ("HEAD","OPTIONS")))
    print(f"{methods:7s} {r.rule}")
