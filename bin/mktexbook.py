#!/usr/bin/python3
import os, sys, re
import fontinfo

def accent(line):
    line = re.sub(r'é',r'\'e',line)
    line = re.sub(r'ñ',r'\~{n}',line)
    line = re.sub(r'á',r'\'{a}',line)
    line = re.sub(r'ô',r'\^{o}',line)
    line = re.sub(r'ö',r'\"{o}',line)
    line = re.sub(r'ó',r'\'{o}',line)
    line = re.sub(r'¿',r'?`',line)
    line = re.sub(r'ç',r'\c{c}',line)
    line = re.sub(r'—',r'---',line)
    line = re.sub(r'í',r'\'{i}',line)
    line = re.sub(r"<'(\w)>",r"\\'{\1}",line)
    line = re.sub(r'<:(\w)>',r'\\"{\1}',line)
    line = re.sub(r'…',r'\ldots ',line)
    line = re.sub(r'©',r'\textcopyright ',line)
    line = re.sub(r'“',"``",line)
    line = re.sub(r'”',"''",line)
    line = re.sub(r'’',"'",line)
    line = re.sub(r'‘',"`",line)
    line = re.sub(r'_',r'{\\textunderscore}',line)
    line = re.sub(r'#',r'\#',line)
    line = re.sub(r'<br>',r'\\\\',line)
    return line

def subtxt(s,d):
    for k in d:
        s = re.sub(r'<<'+k+'>>',str(d[k]),s)
    return s

pagew = 4.25
pageh = 6.88
fontsize = r"\\normalsize"
numbering=False
title = ''
tocfont = r'small'
large = ""
for a in sys.argv[1:]:
    if a == '-fLarge':
        fontsize=r"\\Large"
        continue
    lines = []
    g = re.match(r'^(.*)\.txt$',a)
    if g:
        with open(a,"r") as fr:
            for line in fr.readlines():
                g2 = re.match(r'<bookid=',line)
                if g2:
                    continue
                g2 = re.match(r'<author=',line)
                if g2:
                    continue
                g2 = re.match(r'<geometry=(.*)x(.*)>',line)
                if g2:
                    pagew = float(g2.group(1))
                    pageh = float(g2.group(2))
                    continue
                g2 = re.match(r'<large>',line)
                if g2:
                    large = r"\usepackage[20pt]{extsizes}"
                    continue
                g2 = re.match(r'<cover=(.*)>',line)
                if g2:
                    continue
                g2 = re.match(r'<tocfont=(.*)>',line)
                if g2:
                    tocfont = g2.group(1)
                    continue
                lines += [line]
        out = g.group(1)+".tex"
        print(out)
        fw = open(out,"w")
        print(subtxt(r"""%\pdfminorversion=4
\documentclass[twoside,12pt]{article}
\renewcommand{\contentsname}{}
\usepackage{graphicx}
\usepackage{wrapfig}
\usepackage{fancyhdr}
\usepackage{setspace}
%\usepackage{calligra}
\usepackage{fontspec}
%\usepackage{miama}
%\usepackage[T1,OT1]{fontenc}
%\usepackage[utf8]{inputenc}
\usepackage[none]{hyphenat}
\usepackage{lipsum}% just to generate text for the example
<<large>>
\usepackage[inner=0.75in,outer=0.5in,paperwidth=<<pagew>>in,paperheight=<<pageh>>in,bottom=0.50in,top=1.0in]{geometry}
\sloppy

\usepackage{tgbonum}

\newcommand{\ssection}[1]{%
\section[#1]{\normalfont\scshape\centering #1}}

\newcommand{\susection}[1]{%
\subsection[#1]{\normalfont\scshape\centering #1}}

\newcommand{\setheader}[1]{%
\fancyhead[CE,CO]{#1}}

\newcommand{\hidesection}[1]{%
\section*{\centering #1}\addtocounter{section}{1}}
\usepackage{tocloft}
\usepackage{etoc}
%\renewcommand{\etocaftertitlehook}{\pagestyle{fancy}}

\usepackage{tocloft}
\setlength{\cftbeforesecskip}{3pt}

% Fix the page number on the table of contents
\renewcommand{\etocaftertochook}{\thispagestyle{fancy}}

%\renewcommand\cftchapfont{\small\bfseries}
\renewcommand\cftsecfont{\<<tocfont>>}

%\renewcommand\cftchappagefont{\small\bfseries}
\renewcommand\cftsecpagefont{\<<tocfont>>}

% Turn off section numbering
%\makeatletter
%\renewcommand{\@seccntformat}[1]{}
%\makeatother
\setcounter{secnumdepth}{0}

% Turn of section numbering in toc
\makeatletter
\let\latexl@section\l@section
\def\l@section#1#2{\begingroup\let\numberline\@gobble\latexl@section{#1}{#2}\endgroup}
\makeatother

\fancyhf{}
\renewcommand\headrulewidth{0pt}
%\fancyhead[LO]{\nouppercase\leftmark}
%\fancyhead[RE]{\hdrtitle}
\fancyhead[LE,RO]{\thepage}
\pagestyle{fancy}
%\usepackage{afterpage}
%\DeclareRobustCommand*{\contheading}{%
%  \afterpage{{\normalfont\large\bfseries\centering
%  Table of Contents - Continued\par\bigskip}}}
\makeatletter
\newcommand\iraggedright{%
  \let\\\@centercr\@rightskip\@flushglue \rightskip\@rightskip
  \leftskip\z@skip}
\makeatother
\begin{document}
\setmainfont[
    ItalicFont={[linlibertine_it-4.2.6ro.ttf]}
]{[LinLibertine_R.ttf]}
<<fsize>>
\iraggedright
\  
%\addtocontents{toc}{\contheading}
%\addtocontents{toc}{\protect\setstretch{0.0}}
\addtocontents{toc}{\protect\thispagestyle{empty}}
\pagenumbering{gobble}
""",{"fsize":fontsize,"tocfont":tocfont,"pagew":pagew,"pageh":pageh,"large":large}),file=fw)
        lno = 0
        for line in lines:
            lno += 1
            g = re.match(r'<(no|)chapter="([^"]*)"(\s*sub(?:="([^"]*)"|)|)\s*(?:sect|)>',line)
            if not g:
                g = re.match(r'<(no|)chapter()()>',line)
            if g:
                ch_title = g.group(2)
                ch_title = re.sub(r'^.*?:','',ch_title)
                if g.group(1) == "no":
                    print(r'\vspace*{\fill}',file=fw)
                    print(r'\pagebreak',file=fw)
                    print(r'\hidesection{%s}' % accent(ch_title),file=fw)
                else:
                    print(r'\vspace*{\fill}',file=fw)
                    print(r'\pagebreak',file=fw)
                    print(r'\ ',file=fw)
                    print(r'\vspace{%fin}' % (pagew*0.33),file=fw)
                    if g.group(3) != "":
                        if g.group(4) is None:
                            print(r'\susection{%s}' % accent(ch_title),file=fw)
                        else:
                            print(r'\ssection{%s}' % accent(ch_title),file=fw)
                            print(r'\susection{%s}' % accent(g.group(4)),file=fw)
                    else:
                        print(r'\ssection{%s}' % accent(ch_title),file=fw)
                if not numbering:
                    numbering = True
                    print(r'\pagenumbering{arabic}',file=fw)
                    print(r'\setcounter{page}{2}',file=fw)
                continue
            g = re.match(r'<title="([^"]*)">',line)
            if g:
                if title != '':
                    title += '\\\\\n'
                title += g.group(1)
                continue
            g = re.match(r'<pagebreak>',line)
            if g:
                print(r'\pagebreak',file=fw)
                continue
            g = re.match(r'<blank-lines=(\d+)>',line)
            if g:
                print(r'\vspace{%dpt}' % (int(g.group(1))*12),file=fw)
                print(file=fw)
                continue
            g = re.match(r'<title-page=(true|false)>',line)
            if g:
                print("Skip title page")
                continue
            g = re.match(r'<end>\s*$',line)
            if g:
                break
            g = re.match(r'<(mode|line|note|problem)=".*',line)
            if g:
                continue
            g = re.match(r'<geometry=(.*)x(.*)>',line)
            if g:
                pagew = float(g.group(1))
                pageh = float(g.group(2))
                continue
            g = re.match(r'<img="([^"]*)"(.*)>',line)
            if g:
                opts = g.group(2)
                g2 = re.search(r'\b(\w+)-only\b',opts)
                if g2:
                    if g2.group(1) != "pdf":
                        continue
                width = 8.0
                g2 = re.search(r'\bwidth=(\d+(\.\d+|))px\b',opts)
                if g2:
                    width = float(g2.group(1))
                print(r'\begin{wrapfigure}{l}{%0.2f\textwidth}' % (width/144.0/pagew),file=fw)
                print(r"\includegraphics[width=%0.2fcm]{%s}\mbox{\hspace{0.5em}}" % (.01*width,g.group(1)),file=fw)
                print(r'\end{wrapfigure}',file=fw)
                continue
            g = re.match(r'<authornote="[^"]*">',line)
            if g:
                continue
            g = re.match(r"<authornote='[^']*'>",line)
            if g:
                continue
            g = re.match(r'<header="([^"]*)">',line)
            if g:
                print(r'\setheader{%s}' % g.group(1),file=fw)
                continue
            g = re.match(r'<tocall>',line)
            if g:
                print(r'\begin{center}',file=fw)
                print(r'{\normalfont\large\bfseries Table of Contents}',file=fw)
                print(r'\end{center}',file=fw)
                print(r'\renewcommand{\cftsecleader}{\cftdotfill{\cftdotsep}}',file=fw)
                print(r'\tableofcontents',file=fw)
                continue
            g = re.match(r'<scene(="[^"]*"|)>',line)
            if g:
                print(r'''
\begin{center}
* * *
\end{center}''',file=fw)
                continue
            g = re.match(r'<font="([\w\.-]+)">',line)
            if g:
                #print(r"{\fontfamily{%s}\selectfont " % g.group(1),file=fw)
                if g.group(1) not in fontinfo.fonts:
                    raise Exception("No such font "+g.group(1))
                fonts = fontinfo.fonts[g.group(1)]
                if "tex" not in fonts:
                    raise Exception("No tex entry for font: "+g.group(1))
                print("fonts:",fonts["tex"])
                print(r"{\setmainfont{%s}" % fonts["tex"],end='',file=fw)
                if "size" in fonts:
                    print("[SizeFeatures={Size=%d}]" % fonts["size"],end='',file=fw)
                print(file=fw)
                #print(r"{\calligra\large ",file=fw)
                continue
            g = re.match(r'<font="([\w\.-]+):(\w+)">',line)
            if g:
                #print(r"{\fontfamily{%s}\selectfont\%s " % (g.group(1),g.group(2)),file=fw)
                print(r"{\setmainfont{[%s]}\%s " % (g.group(1),g.group(2)),file=fw)
                #print(r"{\calligra\large ",file=fw)
                continue
            g = re.match(r'</font>',line)
            if g:
                print(r"}",file=fw)
                continue
            g = re.match(r'<center>',line)
            if g:
                print(r'\begin{center}',file=fw)
                continue
            g = re.match(r'</center>',line)
            if g:
                print(r'\end{center}',file=fw)
                continue

            g = re.match(r'<quote>',line)
            if g:
                print(r"\begin{quote}",file=fw)
                continue
            g = re.match(r'</quote>',line)
            if g:
                print(r"\end{quote}",file=fw)
                continue

            g = re.match(r'<quotation>',line)
            if g:
                print(r"\begin{quotation}",file=fw)
                continue
            g = re.match(r'</quotation>',line)
            if g:
                print(r"\end{quotation}",file=fw)
                continue
            g = re.match(r'<toc-pagebreak>',line)
            if g:
                print(r"\addtocontents{toc}{\protect\newpage}",file=fw)
                continue

            g = re.match(r'<large>',line)
            if g:
                #print(r"\usepackage[18pt]{extsizes}",file=fw)
                continue

            g = re.match(r'^\s*<[^>]*>\s*$',line)
            if g:
                raise Exception(line)
            if re.match(r'^\s*#',line):
                continue
            while True:
                nline = re.sub(r'"',"``",line,count=1)
                nline = re.sub(r'"',"''",nline,count=1)
                if nline == line:
                    break
                line = nline
            line = re.sub(r'--','---',line)
            line = re.sub(r'\.\.\.',r'{\ldots}',line)
            line = re.sub(r'<copyright>',r'{$\copyright$}',line)
            line = re.sub(r'<i>',r'\\textit{',line)
            line = re.sub(r'<u>',r'\underline{',line)
            line = re.sub(r'<b>',r'\\textbf{',line)
            line = re.sub(r'<sup>',r'\\textsuperscript{',line)
            line = re.sub(r'</i>',r'}',line)
            line = re.sub(r'</u>',r'}',line)
            line = re.sub(r'</b>',r'}',line)
            line = re.sub(r'</sup>',r'}',line)
            line = re.sub(r'<a[^>]*>','',line)
            line = re.sub(r'</a>','',line)
            line = re.sub(r'<bullet>',r'$\cdot$',line)
            line = re.sub(r'&',r'\&',line)
            line = accent(line)
            for c in line:
                if ord(c) > 128 and lno > 1:
                    raise Exception("Escape character: <"+c+"> "+str(ord(c))+" line: "+str(lno)+", line="+line)
            g = re.match(r'<c>(.*)',line)
            if g:
                print(r'\begin{center}',file=fw)
                print(g.group(1),file=fw)
                print(r'\end{center}',file=fw)
                continue
            if re.search(r'<',line):
                raise Exception(line)
            print(line,end='',file=fw)
    print(r'\end{document}',file=fw)
fw.close()
