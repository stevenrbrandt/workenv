#!/usr/bin/env python3
"""Open a bookmark, a URL, or a local file in the Windows browser.

    ch.py BOOKMARK
    ch.py -u URL
    ch.py -f FILE

FILE may sit on the WSL filesystem or under a Windows drive mount, and the
name may contain spaces. Set CH_BROWSER to an executable path to override
the Chrome/Opera search.
"""

import os
import shutil
import subprocess
import sys
from urllib.parse import quote

# Short name -> (url, description). Description is empty when the URL is enough.
BOOKMARKS = {
    "admin-log" : ("https://docs.google.com/spreadsheets/d/1Ogm8iIgMgJWON0DY6S7Ne9Pua60FuaLQRTSf9qxxNXw/edit?gid=1175039992#gid=1175039992",""),
    "ac": ("https://authorcentral.amazon.com/gp/metrics/rank", ""),
    "bank": ("https://myaccounts.capitalone.com/", ""),
    "beo": ("http://localhost/cios/index.php/python/index.xml", ""),
    "book": ("https://docs.google.com/document/d/1m9JrzgEkme9f3dtKI4xVZGeuUDtv50J2r-m_ZKB3L1Q/edit", ""),
    "cal": ("http://www.google.com/calendar", "My Calendar"),
    "carpetx": ("https://bitbucket.org/eschnett/cactusamrex/wiki/To%20Do%20List", ""),
    "ccano": ("https://lsu.zoom.us/j/587215096", ""),
    "ch": ("http://chromecast.com/setup", ""),
    "chen": ("https://zoom.us/j/9061371972?pwd=R0p1U3lFTm1ZQWJDcTMrTk1GMlJYdz09", ""),
    "chess": ("http://www.chess.com/play/computer", ""),
    "cli": ("http://www.dilbert.com/blog/entry/?EntryID=819&print=1", "Command Line Interface"),
    "ct": ("http://curioustomes.com/wp-admin", ""),
    "d": ("https://drive.google.com/?authuser=0#my-drive", "Google Docs"),
    "discord": ("https://discord.com/channels/222727366449954816/845310120745631764", ""),
    "dooleyzoom": ("https://chapman.zoom.us/j/4445049264", ""),
    "drop": ("https://www.dropbox.com/links/features", ""),
    "fb": ("http://facebook.com", "Facebook"),
    "foundry": ("http://71.236.109.143:30000/setup", ""),
    "git-token": ("https://github.com/settings/tokens", ""),
    "gitter": ("https://gitter.im/EinsteinToolkit/EinsteinToolkit", ""),
    "gmail": ("https://mail.google.com/mail/u/1/#inbox", "Gmail"),
    "guardian": ("https://www.cct.lsu.edu/~mmorris/guardian/docs", ""),
    "images": ("http://images.google.com", "Images"),
    "jaxb": ("http://eclipse.org/ptp/schemas/rm.xsd", "JAXB"),
    "karate": ("https://lsu.zoom.us/j/3873703377?pwd=077883", ""),
    "kdp": ("https://kdp.amazon.com/en_US/bookshelf", ""),
    "leave": ("https://tiger02.apps.lsu.edu/certification_application/leave_certification/", ""),
    "mail": ("http://mail.stevenrbrandt.com", "Mail for my website"),
    "moodle": ("https://moodle3.lsu.edu", ""),
    "nano": ("http://nanowrimo.org", ""),
    "pass": ("https://www.cct.lsu.edu/~sbrandt/passwds.php", ""),
    "phy": ("https://drive.google.com/drive/folders/0B-L3qi_kGiCLN0NRaHZDU3d4Q1k?ths=true", ""),
    "print": ("http://copier-4129.lsu.edu/print/print.php", ""),
    "rd": ("http://www.feedly.com/home#latest", "Feedly Reader"),
    "seq": (
        "http://www.cs.nmsu.edu/~pfeiffer/classes/573/notes/consistency.html",
        "Sequential Consistency vs. strict consistency",
    ),
    "srb": ("http://stevenrbrandt.com", "Home"),
    "svdp": (
        "https://docs.google.com/spreadsheets/d/1y7zz5s2IXb3-cTDbW1T92Z6eT2hB0aDDYpj81EaTZeA/edit?gid=531673938#gid=531673938",
        "",
    ),
    "svn": ("https://svn.cct.lsu.edu/repos", "SVN"),
    "target": ("https://rcam.target.com/", ""),
    "td": ("https://client.schwab.com/Login/SignOn/CustomerCenterLogin.aspx", ""),
    "tests": ("http://einsteintoolkit.org/testsuite_results/index.php", ""),
    "u": ("http://youtube.com", "YouTube"),
    "ult": ("http://dl.acm.org/citation.cfm?id=949336&bnc=1", "Ulterior Reference Counting"),
    "wd": ("https://www.myworkday.com/lsu/d/home.htmld", ""),
    "wifi": ("http://192.168.12.1", ""),
    "wof": ("http://stevenrbrandt.com/worldsof/", ""),
    "wp": ("http://stevenrbrandt.com/wordpress/wp-admin", ""),
    "zoom": ("https://lsu.zoom.us/my/steverbrandt", ""),
}

CHROME_X86 = "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe"
CHROME = "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
OPERA_RELATIVE = (
    "AppData/Local/Programs/Opera Air/opera.exe",
    "AppData/Local/Programs/Opera/opera.exe",
    "AppData/Local/Programs/Opera GX/opera.exe",
    "AppData/Local/Programs/Opera/launcher.exe",
)
PREFERRED_WINDOWS_USERS = ("steve", "sbrandt", "sbrand3")
SKIP_WINDOWS_USERS = {"Public", "Default", "Default User", "All Users"}
WINDOWS_USERS = "/mnt/c/Users"


def usage(file=sys.stdout):
    print("Usage: ch.py [-f FILE] [-u URL] [BOOKMARK ...]", file=file)
    print(file=file)
    print("  -f FILE    open a local file (WSL path or Windows path)", file=file)
    print("  -u URL     open a URL", file=file)
    print("  BOOKMARK   short name from the list below", file=file)
    print(file=file)
    width = max(len(name) for name in BOOKMARKS)
    for name in sorted(BOOKMARKS):
        url, description = BOOKMARKS[name]
        label = description or url
        print(f"  {name:<{width}}  {label}", file=file)


def is_windows_path(path):
    if path.startswith("\\\\") or path.startswith("//"):
        return True
    return len(path) >= 3 and path[1] == ":" and path[2] in "\\/"


def normalize_windows_path(path):
    if path.startswith("//"):
        path = "\\\\" + path[2:]
    return path.replace("/", "\\")


def windows_path_to_file_url(windows_path):
    """Encode a Windows path as a file URL. Spaces become %20."""
    windows_path = normalize_windows_path(windows_path).strip()
    if windows_path.startswith("\\\\"):
        parts = [part for part in windows_path[2:].split("\\") if part]
        if len(parts) < 2:
            raise ValueError(f"incomplete UNC path: {windows_path}")
        host = parts[0]
        rest = "/".join(quote(part, safe="") for part in parts[1:])
        return f"file://{host}/{rest}"
    if len(windows_path) >= 2 and windows_path[1] == ":":
        drive = windows_path[0].upper()
        rest = windows_path[2:].lstrip("\\")
        encoded = "/".join(
            quote(part, safe="") for part in rest.split("\\") if part != ""
        )
        if encoded:
            return f"file:///{drive}:/{encoded}"
        return f"file:///{drive}:/"
    raise ValueError(f"unrecognized Windows path: {windows_path}")


def linux_path_to_windows_fallback(absolute):
    parts = absolute.split("/")
    if len(parts) >= 3 and parts[1] == "mnt" and len(parts[2]) == 1 and parts[2].isalpha():
        drive = parts[2].upper()
        rest = "\\".join(parts[3:])
        if rest:
            return f"{drive}:\\{rest}"
        return f"{drive}:\\"
    distro = os.environ.get("WSL_DISTRO_NAME")
    if not distro:
        raise RuntimeError(
            "wslpath is not available and WSL_DISTRO_NAME is unset; "
            f"cannot convert {absolute}"
        )
    return "\\\\wsl.localhost\\" + distro + absolute.replace("/", "\\")


def linux_path_to_windows(path):
    absolute = os.path.realpath(os.path.expanduser(path))
    wslpath = shutil.which("wslpath")
    if wslpath is None:
        return linux_path_to_windows_fallback(absolute)
    completed = subprocess.run(
        [wslpath, "-w", absolute],
        check=False,
        capture_output=True,
        text=True,
    )
    windows = completed.stdout.strip()
    if completed.returncode != 0 or not is_windows_path(windows):
        detail = completed.stderr.strip() or windows or "wslpath produced no Windows path"
        raise RuntimeError(f"cannot convert {absolute}: {detail}")
    return windows


def file_url(path):
    if is_windows_path(path):
        windows = normalize_windows_path(path)
    else:
        windows = linux_path_to_windows(path)
    return windows_path_to_file_url(windows)


def collect_targets(argv):
    """Turn argv into the URLs the browser should open."""
    targets = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "-f":
            index += 1
            if index >= len(argv) or argv[index] == "":
                raise ValueError("-f needs a filename")
            targets.append(file_url(argv[index]))
        elif arg == "-u":
            index += 1
            if index >= len(argv) or argv[index] == "":
                raise ValueError("-u needs a URL")
            targets.append(argv[index])
        elif arg in BOOKMARKS:
            targets.append(BOOKMARKS[arg][0])
        else:
            raise ValueError(f"No such bookmark: {arg}")
        index += 1
    return targets


def windows_user_dirs():
    if not os.path.isdir(WINDOWS_USERS):
        return []
    names = [
        name
        for name in os.listdir(WINDOWS_USERS)
        if name not in SKIP_WINDOWS_USERS
        and os.path.isdir(os.path.join(WINDOWS_USERS, name))
    ]
    preferred = [name for name in PREFERRED_WINDOWS_USERS if name in names]
    rest = sorted(name for name in names if name not in preferred)
    return [os.path.join(WINDOWS_USERS, name) for name in preferred + rest]


def find_browser():
    override = os.environ.get("CH_BROWSER")
    if override:
        if os.path.isfile(override) and os.access(override, os.X_OK):
            return override
        raise RuntimeError(f"CH_BROWSER is not an executable file: {override}")
    candidates = [CHROME_X86]
    for home in windows_user_dirs():
        for relative in OPERA_RELATIVE:
            candidates.append(os.path.join(home, relative))
    candidates.append(CHROME)
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def open_in_browser(urls, browser):
    # Windows Chrome refuses to start when its working directory is a Linux path.
    cwd = "/mnt/c" if os.path.isdir("/mnt/c") else None
    process = subprocess.Popen(
        [browser, *urls],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        code = process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        return
    if code != 0:
        raise RuntimeError(f"{browser} exited with status {code}")


def main(argv):
    if not argv or "-h" in argv or "--help" in argv:
        usage()
        return 0
    try:
        targets = collect_targets(argv)
        browser = find_browser()
        if browser is None:
            print("No Chrome or Opera executable found under /mnt/c", file=sys.stderr)
            return 1
        open_in_browser(targets, browser)
    except (ValueError, RuntimeError) as error:
        print(error, file=sys.stderr)
        if isinstance(error, ValueError):
            usage(sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
