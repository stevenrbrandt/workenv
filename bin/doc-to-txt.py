#!/usr/bin/python3
import re
import zipfile
import subprocess as s

import xml.etree.ElementTree as ET

use_italics = True
last_was_tag = False

lastP = False
comments = {}

def fix(s):
    s = re.sub(r'…','...',s)
    s = re.sub(r"’","'",s)
    s = re.sub(r'“','"',s)
    s = re.sub(r'”','"',s)
    s = re.sub(r'\s*—\s*',"--",s)
    s = re.sub(r'</i><i>',"",s)
    return s

def save(content,file_name):
    pass
    #with open(file_name,"w") as fd:
    #    p = s.Popen(["xmllint", "--format", "-"], stdout=fd, stdin=s.PIPE)
    #    p.stdin.write(content)

def get_name(elem):
    if elem == None:
        return ''
    s = str(elem)
    g = re.match(r".*}([\w:]+)('|$)",s)
    if not g:
        raise Exception(str(elem))
    return g.group(1)

def get_attr(elem,name):
    if elem == None:
        return None
    for k in elem.attrib:
        if get_name(k) == name:
            return elem.attrib[k]
    return None

def fmt_attr(elem):
    if elem == None:
        return ''
    if type(elem) == str:
        return elem
    a = elem.attrib
    s = '{'
    sep = ''
    for k in a:
        sep =','
        s += get_name(k)
        s += '='
        s += a[k]
        s += sep
    s += '}'
    return s

def show_elem(elem):
    return get_name(elem)+fmt_attr(elem)

def do_elem(elem,ind='',quote=False):
    global lastP, last_was_tag
    props = {
        "text":"",
        "italic":False,
        "bold":False,
        "center":False,
        "quote":quote,
        "cid":[]
    }
    #print(ind,'<',show_elem(elem),'>',sep='')
    name = get_name(elem)
    if name == 'p':
        props["quote"]=False
    if name == "del":
        return props
    if name == "ind":
        if not props["quote"] and get_attr(elem,"left"):
            if not lastP:
                if use_italics:
                    print("<quote>")
                    print()
            lastP = True
            props["quote"] = True
    elif name == "i":
        props["italic"] = True
    elif name == "b":
        props["bold"] = True
    elif name == "jc" and get_attr(elem,"val") == "center":
        props["center"] = True
    elif name == "commentRangeStart":
        props["cid"] += [get_attr(elem,"id")]
    elif name == "t":
        #print("<",show_elem(elem),":",show_elem(h),":",show_elem(h2),">: {",elem.text,"}",sep='')
        #print(ind,"{",elem.text,"}",sep='')
        preserve = False
        for k in elem.attrib:
            if get_name(k) == "space" and elem.attrib[k] == "preserve":
                preserve = True
                break
        if preserve:
            props["text"] += elem.text
        else:
            props["text"] += elem.text.strip()
    else:
        for e in elem:
            p = do_elem(e,ind+'  ',props["quote"])
            props["text"] += p["text"]
            if p["italic"]:
                props["italic"] = True
            if p["bold"]:
                props["bold"] = True
            if p["center"]:
                props["center"] = True
            if p["quote"]:
                props["quote"] = True
            for vs in p["cid"]:
                props["cid"] += [vs]
    if name == "r":
        if props["italic"] and not props["quote"]:
            if props["text"].strip() == "Inside":
                print(props,file=sys.stderr)
            if use_italics:
                props["text"] = "<i>"+props["text"]+"</i>"
            else:
                props["text"] = props["text"]
            props["italic"] = False
        elif props["bold"]:
            if use_italics:
                props["text"] = "<b>"+props["text"]+"</b>"
            else:
                props["text"] = props["text"]
            props["bold"] = False
        else:
            pass #print(props["text"],end='')
    #print(ind,"</",show_elem(elem),'>',sep='')
    if name == "p":
        off = False
        if lastP and not props["quote"]:
            if use_italics:
                print("</quote>")
                print()
            off = True
            lastP = False
        txt = props["text"].strip()
        if txt=='':
            return props
        if props["center"] and not props["quote"]:
            #print("<p style='text-align: center'>",end='')
            if re.match(r"^\s*\*\s*\*\s*\*\s*$",txt) or re.match(r'^\s*#\s*',txt):
                print("\n<scene>",end='')
            else:
                txt = re.sub(r'Chapter\s+\d+:?\s*','',txt)
                print("\n<chapter=\"%s\">" % txt,end='')
        elif re.match(r'^\s*#\s*',txt):
            print("\n<scene>",end='')
        else:
            #print("<p>",end='')
            is_tag = re.search(r'>\s*$',txt) is not None
            if is_tag and re.search(r'</[ib]>\s*$',txt):
                is_tag = False
            if (not last_was_tag) or (not is_tag):
                #if is_tag:
                #    print(end='[1]')
                #if last_was_tag:
                #    print(end='[2]')
                print()
            print(fix(txt.strip()),end='')
            last_was_tag = is_tag
            #else:
            #    print()
            #print("</p>")
        for vs in props["cid"]:
            if vs in comments:
                print('\n#',fix(comments[vs].strip()),end='')
        print()
        props["text"] = ''
        props["center"] = False
        lastP = props["quote"]
        props["quote"] = False
    return props

def get_comments(tree,id='?',author=None):
    global comments
    name = get_name(tree)
    if name == "comment":
        id = get_attr(tree,"id")
        author = get_attr(tree,"author")
    elif name == "t":
        if author is not None:
            comments[id] = author+": "+tree.text
        else:
            comments[id] = tree.text
        #print("C:",id,"->",tree.text,file=sys.stderr)
    for e in tree:
        get_comments(e,id,author)

def get_docx_text(path):
    """
    Take the path of a docx file as argument, return the text in unicode.
    """
    document = zipfile.ZipFile(path)
    try:
        xml_content = document.read('word/comments.xml')
        save(xml_content,"comments.xml")
        tree = ET.fromstring(xml_content)
        get_comments(tree)
    except:
        pass
    #with open("comments.xml","w") as fd:
    #    fd.write(xml_content.decode())
    xml_content = document.read('word/document.xml')
    save(xml_content,"document.xml")
    #with open("text.xml","w") as fd:
    #    fd.write(xml_content.decode())
    document.close()
    tree = ET.fromstring(xml_content)
    #print(tree)
    #print(dir(tree))
    do_elem(tree,quote=False)

import sys

arg = None
for a in sys.argv:
    if a == '-i':
        use_italics = False
    else:
        arg = a

get_docx_text(arg)
