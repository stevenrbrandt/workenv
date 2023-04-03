#!/bin/bash

echo Add Upstream:
echo git remote add upstream https://github.com/zachetienne/nrpytutorial
echo
echo Merge upstream:
echo git fetch upstream
echo git merge upstream/master
echo git vimdiff upstream/master
