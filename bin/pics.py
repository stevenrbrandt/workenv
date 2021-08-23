#!/usr/bin/env python3

import os, re
files = []
for f in os.listdir("."):
    if re.search(r'(?i)\.(png|jpe?g|gif|tif|bmp)', f):
        files += [f]

with open("index.html", "w") as fd:
    for f in files:
        print(f"""
<a style="float: right" href='file:{f}'>
  <img width=400 src='file:{f}' alt='{f}' />
  <div>{f}</div>
</a>
""", file=fd)
