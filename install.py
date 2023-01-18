#/usr/bin/env python3
from __future__ import print_function
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
if [ "$PYTHONUSERBASE" = "" ]
then
    export PATH="$PATH:$HOME/.local/bin"
else
    export PATH="$PATH:$PYTHONUSERBASE/bin"
fi

if [ -d ~/workenv/py ]
then
    export PYTHONPATH="$HOME/workenv/py:$PYTHONPATH"
fi

if [ -d ~/repos/workenv/py ]
then
    export PYTHONPATH="$HOME/repos/workenv/py:$PYTHONPATH"
fi

alias vi=vim
alias vdiff="vimdiff -c 'set wrap' -c 'wincmd w' -c 'set wrap'"
alias twait='fg && trun -n echo success || trun -n echo failure'
alias spack-load='source spack-load.sh'
alias show-cursor='echo -en "\e[?25h"'
alias today='date +%m-%d-%Y'
alias pip3='python3 -m pip'
if [ -r /usr/bin/hostname -o -r /bin/hostname ]
then
  HOST=$(hostname)
else
  HOST=""
fi
if [ "$HOST" = "" ] && [ -r /usr/bin/uname -o -r /bin/uname ]
then
  HOST=$(uname -n)
fi
if [ "$HOST" = "" ] && [ -r /etc/hostname ]
then
  HOST=$(cat /etc/hostname)
fi
if [ "$HOST" = "" ]
then
  HOST=Linux
fi
if [ "$(id -u)" = 0 ]
then
    export PS1_COLOR='\\[\\033[33m\\]$HOST \\[\\033[93m\\]$(basename "$PWD")\\[\\033[0m\\]# '
    export PS1_BW='$HOST $(basename "$PWD")# '
    PS1=$PS1_COLOR
else
    export PS1_COLOR='\\[\\033[36m\\]$HOST \\[\\033[32m\\]$(basename "$PWD")\\[\\033[0m\\]$ '
    export PS1_BW='$HOST $(basename "$PWD")$ '
    PS1=$PS1_COLOR
fi
alias ps1color='PS1=$PS1_COLOR'
alias ps1bw='PS1=$PS1_BW'
unset PROMPT_COMMAND
export OMP_NUM_THREADS=1
export LANG=en_US.UTF-8
export VISUAL=vi
shopt -s histappend                      # append to history, don't overwrite it
export PROMPT_COMMAND="history -a; history -c; history -r; $PROMPT_COMMAND"
export HISTSIZE=100000
alias envup='(cd $(dirname $(dirname $(which mkrtf.pl))) ; git pull ; python3 ./install.py ) ; source ~/.bashrc'
alias git-clear-passwd='git config --global credential.helper store'
if [ "$LOGGED_IN" != "yes" ]
then
    telegram-send "$HOST-$(date)"
    LOGGED_IN=yes
fi
""".format(here=here),file=fd)

vimrc = os.path.join(home,".vimrc")
if not os.path.exists(vimrc):
    with open(vimrc,"w") as fd:
        print("""
set ai nu ic sw=4 ts=4 expandtab hlsearch linebreak
colorscheme torture
syn on
if has("autocmd")
  au BufReadPost * if line("'\\"") > 0 && line("'\\"") <= line("$") | exe "normal! g`\\"" | endif
endif
set ambw=double 
""".format(here=here),file=fd)

vim_dir = os.path.join(home, ".vim", "colors")
if not os.path.exists(vim_dir):
    os.makedirs(vim_dir)
torture = os.path.join(vim_dir, "torture.vim")

if not os.path.exists(torture):
    with open(torture,"w") as fd:
        print("""
" Vim color file
" Maintainer:   Your name <youremail@something.com>
" Last Change:  
" URL:		

" cool help screens
" :he group-name
" :he highlight-groups
" :he cterm-colors

" your pick:
set background=light
hi clear
if exists("syntax_on")
    syntax reset
endif
let g:colors_name="torture"

"hi Normal

" OR

" highlight clear Normal
" set background&
" highlight clear
" if &background == "light"
"   highlight Error ...
"   ...
" else
"   highlight Error ...
"   ...
" endif

" A good way to see what your colorscheme does is to follow this procedure:
" :w 
" :so % 
"
" Then to see what the current setting is use the highlight command.  
" For example,
" 	:hi Cursor
" gives
"	Cursor         xxx guifg=bg guibg=fg 
 	
" Uncomment and complete the commands you want to change from the default.

"hi Cursor		
"hi CursorIM	
"hi Directory	
"See https://github.com/guns/xterm-color-table.vim

hi DiffAdd guifg=white guibg=darkblue
hi DiffAdd ctermfg=white ctermbg=darkblue

hi DiffChange guifg=white guibg=darkred
hi DiffChange ctermfg=white ctermbg=darkred

hi DiffText guifg=white guibg=darkblue
hi DiffText ctermfg=white ctermbg=darkblue

hi italics  guifg=darkblue guibg=black
hi italics  ctermfg=darkblue ctermbg=black

hi quote guifg=green guibg=black
hi quote ctermfg=black ctermbg=black

hi quoteerror ctermfg=black ctermbg=red
hi quixote ctermfg=black ctermbg=cyan
hi letter_a ctermfg=black ctermbg=cyan

hi DiffDelete guifg=white guibg=darkblue
hi DiffDelete ctermfg=white ctermbg=darkblue

hi ErrorMsg	guifg=red term=bold
hi ErrorMsg	ctermfg=red term=bold
"hi VertSplit	
"hi Folded		
"hi FoldColumn	
"hi IncSearch	
"hi LineNr		
"hi ModeMsg		
"hi MoreMsg		
"hi NonText		
"hi Question	
"hi Search		
"hi SpecialKey	
"hi StatusLine	
"hi StatusLineNC	
"hi Title		
"hi Visual		
"hi VisualNOS	
"hi WarningMsg	
"hi WildMenu	
"hi Menu		
"hi Scrollbar	
"hi Tooltip		

" syntax highlighting groups
" term=bold,standout,underline,reverse
hi Comment ctermfg=lightblue term=bold
hi Comment guifg=lightblue term=bold
"hi Constant	
"hi Identifier	
"hi Statement ctermfg=royalblue term=bold
hi Statement guifg=olivedrab3 term=bold
"hi PreProc	
"hi Type		
"hi Special	
"hi Underlined	
"hi Ignore		
"hi Error		
"hi Todo	ctermbg=red term=bold
hi Todo term=standout ctermbg=Yellow ctermfg=Black guifg=Blue guibg=Yellow
hi Search ctermfg=Yellow ctermbg=Black guibg=Black guifg=Yellow
""",file=fd)

gitconf = os.path.join(home,".gitconfig")
if not os.path.exists(gitconf):
    with open(gitconf,"w") as fd:
        print("""
[user]
    email = sbrandt@cct.lsu.edu
    name = Steven R. Brandt
[diff]
  #external = git_diff_wrapper
[pager]
  #diff =
[http]
[merge]
    tool = meld
[branch]
    autosetuprebase = always
#[branch "master"]
#   rebase = true
[credential]
    #helper = osxkeychain
[core]
    #autocrlf = input
  whitespace = -trailing-space,-indent-with-non-tab,-tab-in-indent
    autocrlf = false
    safecrlf = false
[credential]
    helper = store
[push]
    default = current
[pull]
    default = current
[alias]
    co = checkout
    vimdiff = -c diff.external=git_diff_wrapper -c pager.diff=0 diff
    clear-passwd = config --global credential.helper store
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
        call(["sudo"]+cmd)
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
if which("hostname") is None:
    sucall([installer[1],"install","-y","hostname"])

pub_key="""ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAACAQDEHHb1f5hg62cg1VBe4AJgz0HaeIMWYhcH2PpkwubWFYmKY5ndTYwx64BaJ/FYgRxubLfBtve6CVTSX4LT488pXyLFbc5X0vS4ibYbJ3a/vctjWeGLgnXELsrxlNungT/hM+ho3JkRhjjMLuTExFRSDFfG57GQjjemiX5nWWLVNdO2N4WQZdozrCBsbH5xFtxfaW3KGvMYR6+s/vyk+VNP6mJ027f3590mrI6mK/VeBdh5Nga1l04wLzoi6rj+PZnlpRTmV3F10NN0LkyrezfcbtX2bWYOSR6Mt5GH7S6NKOaXUDlktQdg+k0731xCdd/u9arg8lXasfuxoCkmYpKkamLJgk4QuabYsrxNhif6+o0trPJ9uYPu5AXwocwbVlfBpUUXJwHFDdTjSaUVDIwmzYQdX4N2vAFzWUiKRu0yFem8UoLWeCl0OE+EL8t4KqQASSkXwrko6nyDTSVq+DPEKRg0UDbH41tIldLUHZgxlpJ4kODmKcCXFS15dF+SOseq+woZUE9IuKEFtPH6rukPZbz2j9boATDPTkDI+bK/aouQCGhlghmKoGGURIsCjJ4CIC9zi3Hgr7/yxz+J5lKC1g/VD1KE+VckE32V4fZAOfcs1heZKHYii3pVwB7pHWxUl/rlzK6jCh/Gce8Jj6iE/bASLcalcWvV2+GceJFX2Q== sbrandt@localhost.localdomain"""

ssh_dir = os.path.join(home,".ssh")
if not os.path.exists(ssh_dir):
    os.makedirs(ssh_dir)
os.chmod(ssh_dir,0o0700)
os.chmod(home,0o755)
auth_keys = os.path.join(ssh_dir,"authorized_keys")
auth_keys_c = ""
if os.path.exists(auth_keys):
    with open(auth_keys,"r") as fd:
        auth_keys_c = fd.read()
if pub_key not in auth_keys_c:
    with open(auth_keys,"a") as fd:
        print(pub_key,file=fd)
