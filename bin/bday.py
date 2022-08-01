#!/usr/bin/env python3
from random import randint
import sys

icons = ["🎂","🎈","🎉","🥳","🎁"]

num = int(sys.argv[1])
s = ""
for n in range(num):
    r = randint(0,len(icons)-1)
    s += icons[r]
print(s)
