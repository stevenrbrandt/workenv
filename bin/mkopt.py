import re, os, sys
config = sys.argv[1]

capabilities = dict()

basedir = f"configs/{config}/bindings/Configuration/Capabilities"
for fn in os.listdir(basedir):
    if fn.endswith(".defn"):
        full = os.path.join(basedir, fn)

        capability = None
        with open(full, "r") as fd:
            for line in fd.readlines():
                if g := re.match(r'HAVE_CAPABILITY_(\w+)', line):
                    capability = g.group(1).upper()
                    if capability == "OPENPMD_API":
                        capability = "OPENPMD"

        if capability is None:
            continue

        printed = False

        with open(full, "r") as fd:
            for line in fd.readlines():
                if g := re.match("^" + capability + r"_(\w+)\s*=\s*(.*\S)", line):
                    #print("FOUND:", capability, g.group(1), "->", g.group(2))
                    c = capabilities.get(capability, None)
                    if c is None:
                        c = dict()
                        capabilities[capability] = c
                    if g.group(1) not in ["BUILD"]:
                        c[g.group(1)] = g.group(2)
                        if not printed:
                            print(capability, "<-", full)
                            printed = True

with open(f"configs/{config}/OptionList", "r") as fdr:
    with open("local.cfg", "w") as fdw:
        for line in fdr.readlines():
            if g := re.match(r'([A-Z][A-Z0-9]*)_(\w+)\s*=', line):
                if g.group(1) in capabilities and g.group(2) in capabilities[g.group(1)]:
                    continue
            print(line, end='', file=fdw)
        for c, tab in capabilities.items():
            for item, v in tab.items():
                print(f"{c}_{item} = {v}", file=fdw)
