with open("reports/compositional_failures_audit.md", "r", encoding="utf-8") as f:
    text = f.read()

sections = text.split("### Failure ")
for sec in sections[1:15]:
    lines = [l.strip() for l in sec.split("\n") if l.strip()]
    inp = lines[0]
    exp = [l for l in lines if "Canonical Expected" in l]
    ret = [l for l in lines if "Retrieved (Top 5)" in l]
    mis = [l for l in lines if "Missing in Top 10" in l]
    print(inp)
    if exp: print(" ", exp[0])
    if ret: print(" ", ret[0])
    if mis: print(" ", mis[0])
