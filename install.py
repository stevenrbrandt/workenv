#/usr/bin/env python3
import os
from subprocess import call

home = os.environ["HOME"]
here = os.getcwd()

linetoadd = "source ~/.bashaux"
found = False

with open(os.path.join(home,".bashrc"),"r") as fd:
    for line in fd.readlines():
        if linetoadd in line:
            found = True
            break

if not found:
    with open(os.path.join(home,".bashrc"),"a") as fd:
        print(linetoadd,file=fd)

with open(os.path.join(home,".bashaux"),"w") as fd:
    print("""
set -o vi
export PATH="{here}/bin:$HOME/bin:$PATH"
alias vi=vim
""".format(here=here),file=fd)

vimrc = os.path.join(home,".vimrc")
if not os.path.exists(vimrc):
    with open(vimrc,"w") as fd:
        print("""
set ai nu ic sw=4 ts=4 expandtab
colorscheme elflord
syn on
if has("autocmd")
  au BufReadPost * if line("'\\"") > 0 && line("'\\"") <= line("$") | exe "normal! g`\\"" | endif
endif
""".format(here=here),file=fd)

gitconf = os.path.join(home,".gitconfig")
if not os.path.exists(gitconf):
    with open(gitconf,"w") as fd:
        print("""
[user]
	email = sbrandt@cct.lsu.edu
	name = Steven R. Brandt
[diff]
  external = git_diff_wrapper
[pager]
  diff =
[http]
[merge]
	tool = meld
[branch]
	autosetuprebase = always
#[branch "master"]
#	rebase = true
[credential]
	#helper = osxkeychain
[core]
	#autocrlf = input
  whitespace = -trailing-space,-indent-with-non-tab,-tab-in-indent
	autocrlf = false
	safecrlf = false
[credential]
	helper = store
[init]
  templatedir=/usr/lib/git-core/templates
""".format(here=here),file=fd)

def which(cmd):
    for p in os.environ["PATH"].split(os.pathsep):
        f = os.path.join(p,cmd)
        if os.path.exists(f):
            return (f, cmd)
    return None

installer = which("apt-get")
if installer is None:
    installer = which("dnf")
if installer is None:
    installer = which("yum")
if installer is None:
    installer = which("zypper")

def sucall(cmd):
    if os.getuid() == 0:
        call(cmd)
    elif which("sudo") is not None:
        call(cmd)
    else:
        print("Skipping:",cmd)

if which("vim") is None:
    sucall([installer[1],"install","-y","vim"])
if which("find") is None:
    sucall([installer[1],"install","-y","findutils"])
if which("which") is None:
    sucall([installer[1],"install","-y","which"])
if which("file") is None:
    sucall([installer[1],"install","-y","file"])
if which("perl") is None:
    sucall([installer[1],"install","-y","perl"])
