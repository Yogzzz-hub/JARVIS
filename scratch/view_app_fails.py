with open("reports/slot_failure_analysis.md", "r", encoding="utf-8") as f:
    text = f.read()

sections = text.split("### Failure ")
count = 0
for sec in sections[1:]:
    if "**Root Cause**: APP" in sec:
        lines = [line.strip() for line in sec.split("\n") if line.strip()]
        inp = lines[0]
        exp = [l for l in lines if 'Expected Slots' in l]
        act = [l for l in lines if 'Actual Slots' in l]
        print(inp)
        if exp: print(" ", exp[0])
        if act: print(" ", act[0])
        count += 1
        if count >= 20:
            break
