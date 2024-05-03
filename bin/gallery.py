import os
import re
from PIL import Image

files = []
for f in os.listdir("."):
    if re.search(r'(?i)\.(png|jpe?g|gif|tif|bmp)', f):
        files += [f]

def sortkey(fn):
    image = Image.open(fn)
    key = image._getexif()
    #print(fn,"->",key)
    return str(key)

files = sorted(files, key=sortkey)

with open("index.html","w") as fd:
    print(f"""
<!DOCTYPE html>
<html>
<head>
<style>
div.gallery {{
  margin: 5px;
  border: 1px solid #ccc;
  float: left;
  width: 180px;
}}

div.gallery:hover {{
  border: 1px solid #777;
}}

div.gallery img {{
  width: 100%;
  height: auto;
}}

div.desc {{
  padding: 15px;
  text-align: center;
}}
</style>
</head>
<body>
""",file=fd)

    for file in files:
        print(f"""
<div class="gallery">
  <a target="_blank" href="{file}">
    <img height="100" src="{file}" alt="{file}" width="600" height="400">
  </a>
  <div class="desc">{file}</div>
</div>
""",file=fd)

    print(f"""
</body>
</html>
""",file=fd)
