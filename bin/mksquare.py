import sys
import re
from subprocess import call

data = []

srcf = sys.argv[1]
dst = re.split(r'\.', srcf)
dst[-2] += "_sq"
dstf = ".".join(dst)
dst[-1] = "ppm"
ppmf = ".".join(dst)
print(dstf)
call(["convert",srcf,"-compress","none",ppmf])
with open(ppmf,"r") as fd:
    for line in  fd.readlines():
        data += [re.split(r'\s+', line.strip())]
for datum in data[0:3]:
    print(datum)

n = 0
for datum in data[3:]:
    n += len(datum)
nx = int(data[1][0])
ny = int(data[1][1])
n2 = nx*ny*3
assert n==n2, f"diff {n-n2}"

pixels = []
for datum in data[3:]:
    pixels += datum

nn = max(nx,ny)
image = []
pi = 0
for j in range(ny):
    row = []
    for i in range(nx):
        pixel = (pixels[pi], pixels[pi+1], pixels[pi+2])
        pi += 3
        row += [pixel]
    image += [row]
mxc = int(data[2][0])
white = (mxc,mxc,mxc)
while nx < nn:
    if nx % 2 == 0:
        for j in range(len(image)):
            image[j] = [white]+image[j]
    else:
        for j in range(len(image)):
            image[j] += [white]
    nx += 1
white_row = [white]*nx
while ny < nn:
    if ny % 2 == 0:
        image = [white_row] + image
    else:
        image += [white_row]
    ny += 1
assert nx==nn
assert ny==nn
with open(ppmf,"w") as fd:
    print("P3",file=fd)
    print(nn,nn,file=fd)
    print(mxc,file=fd)
    for row in image:
        for pixel in row:
            for color in pixel:
                print(color,file=fd,end=' ')
        print(file=fd)
call(["convert",ppmf,dstf])
