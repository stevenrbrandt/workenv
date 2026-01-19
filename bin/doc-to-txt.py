#!/usr/bin/python3
import re
import zipfile
import subprocess as s

import xml.etree.ElementTree as ET

verbose = False
use_italics = True
last_was_tag = False

lastP = False
comments = {}

def is_last(iterable):
    it = iter(iterable)
    try:
        e = next(it)
        while True:
            try:
                nxt = next(it)
                yield (False, e)
                e = nxt
            except StopIteration:
                yield (True, e)
                break
    except StopIteration:
        pass # Handles empty iterators

def nz(x):
    return not(x is None or x == 0)

def fix(s):
    s = re.sub(r'…','...',s)
    s = re.sub(r"’","'",s)
    s = re.sub(r'“','"',s)
    s = re.sub(r'”','"',s)
    s = re.sub(r'\s*–\s*','--',s)
    s = re.sub(r'\s*—\s*',"--",s)
    s = re.sub(r'</i>\s*<i>',"",s)
    s = re.sub(r'<i>\s*</i>',"",s)
    s = re.sub(r'</b>\s*<b>',"",s)
    s = re.sub(r'<b>\s*</b>',"",s)
    s = re.sub(r'<i> ',r' <i>',s)
    s = re.sub(r' </i>',r'</i> ',s)
    #s = re.sub(r'^\s+','',s)
    #s = re.sub(r'\s+$','',s)
    return s

def dump(fd, elem, ind=0):
    name = re.sub(r'.*}','',elem.tag)
    print(" "*ind, name, sep='', file=fd)
    for elem2 in elem:
        dump(fd, elem2, ind+2)
    if name == "t":
        print(" "*(ind+2),elem.text,file=fd)

def save(content,file_name):
    pass
    #with open(file_name,"w") as fd:
    #    p = s.Popen(["xmllint", "--format", "-"], stdout=fd, stdin=s.PIPE)
    #    p.stdin.write(content)

def get_name(elem):
    if elem == None:
        return ''
    if type(elem) == str:
        return re.sub(r'.*}','',elem)
    s = elem.tag
    sc = re.sub(r'.*}','',s) # fix name to get rid of URL
    #if hasattr(elem, "attrib"):
    #    for k in elem.attrib:
    #        kc = re.sub(r'.*}','', k) # fix name to get rid of URL
    #        if kc == "val":
    #            # False is encoded as the str "0"
    #            if sc in ["strike","italic","bold"] and elem.attrib[k] == "0":
    #                return ''
    return sc

def get_attr(elem,name):
    if elem == None:
        return None
    for k in elem.attrib:
        ks = re.sub(r'.*}','',k)
        if ks == name:
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

def get_text(elem):
    text = ""
    name = get_name(elem)
    if name == "t":
        if elem.text is not None:
            text += elem.text
    else:
        for elem2 in elem:
            text += get_text(elem2)
    return text

def get_props(elem, props=None, trace=False):
    if props is None:
        props = {
            "italic":False,
            "bold":False,
            "center":False,
            "strike":False,
            "quote":False,
            "pStyle":"text",
            "ind":None,
            "cid":[]
        }
    if elem is None:
        return props
    for elem2 in elem:
        name = get_name(elem2)
        val = get_attr(elem2, "val")
        if trace:
            print(">>",name,val, file=sys.stderr)
        if name == "i":
            props["italic"] = val != "0"
        elif name == "rStyle" and val == "Emphasis":
            props["italic"] = True
        elif name == "b":
            props["bold"] = val != "0"
        elif name == "strike":
            props["strike"] = val != 0
        elif name == "pStyle":
            props["pStyle"] = val
        elif name == "jc" and get_attr(elem2,"val") == "center":
            props["center"] = True
        elif name == "commentRangeStart":
            props["cid"] += [get_attr(elem2,"id")]
        elif name == "ind":
            left = get_attr(elem2, "left")
            right = get_attr(elem2, "right")
            props["ind"] = (left, right)
            props["quote"] = left not in [0, None] and right not in [0, None]

        #if elem2.text is None:
        #    props["text"] = ""
        #elif get_attr(elem2, "space") == "preserve":
        #    props["text"] = elem2.text
        #else:
        #    props["text"] = elem2.text.strip()

        get_props(elem2, props, trace)

    return props

def do_elem(elem,props=None,last_elem=False):
    global lastP, last_was_tag, verbose
    name = get_name(elem)
    if name == "del":
        return ""
    elif name == "r":
        if props is not None:
            props1 = props
        else:
            props1 = get_props(None)
        props2 = get_props(elem)
        props2["text"] = get_text(elem)
        if props2["italic"] and not props1["quote"]:
            if props2["text"] != "":
                props2["text"] = "<i>"+props2["text"]+"</i>"
        if props2["bold"]:
            if props2["text"] != "":
                props2["text"] = "<b>"+props2["text"]+"</b>"
        if props2["strike"]:
            if props2["text"] != "":
                props2["text"] = "<u>"+props2["text"]+"</u>"
        return props2["text"]
    elif name == "p":
        off = False
        props2 = get_props(elem)
        props2["text"] = get_text(elem)
        is_tag = True
        if not lastP and props2["quote"]:
            print("<quote>")
        if lastP and not props2["quote"]:
            if use_italics:
                print("</quote>")
            off = True
        lastP = props2["quote"]
        txt = props2["text"]
        if props2["pStyle"] == "Heading1":
            print(f'<title="{fix(txt.strip())}">')
        elif props2["pStyle"] == "Heading2":
            txt = fix(re.sub(r'^Chapter.*?:\s*','',txt).strip())
            if len(txt) > 0:
                print(f'<chapter="{txt.strip()}">')
        elif props2["pStyle"] == "Heading3":
            txt = fix(re.sub(r'^Scene.*?:\s*','',txt).strip())
            if txt in ["#","***","###"]:
                print("<scene>")
            else:
                print(f'<scene="{txt}">')
        elif props2["center"] and not props2["quote"]:
            if re.match(r"^\s*\*\s*\*\s*\*\s*$",txt) or re.match(r'^\s*#\s*',txt):
                print("<scene>")
            else:
                txt = fix(re.sub(r'Chapter\s+\d+:?\s*','',txt).strip())
                if len(txt) == 0:
                    pass
                elif re.match(r'^\s*(<i>|)#(</i>|)\s*',txt):
                    print("<scene>")
                else:
                    print("<chapter=\"%s\">" % re.sub(r'<\/?b>','',txt))
        elif re.match(r'^\s*#\s*',txt):
            print("<scene>")
        else:
            is_tag = False
            new_txt = ""
            for last,elem2 in is_last(elem):
                new_txt += do_elem(elem2,props2,last)
            new_txt = fix(new_txt.strip())
            if len(new_txt) > 0:
                print(new_txt)
                for vs in props2["cid"]:
                    if vs in comments:
                        print('#',comments[vs].strip(),end='')
                print()
        if is_tag:
            print()
    else:
        new_text = ""
        for elem2 in elem:
            new_text += do_elem(elem2)
        return new_text
    return ""

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
    do_elem(tree)

import sys

arg = None
for a in sys.argv:
    if a == '-i':
        use_italics = False
    else:
        arg = a

get_docx_text(arg)
