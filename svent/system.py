import glob
import os
import re
import shutil
import subprocess


def installed_version(package):

    if not shutil.which("dpkg-query"):
        return None
    proc = subprocess.run(
        ["dpkg-query", "-W", "-f=${db:Status-Abbrev}\t${Version}", package],
        capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    status, _, version = proc.stdout.partition("\t")
    return version if status.startswith("ii") else None


def run_functional_test(tool, timeout=30):
    argv = tool["functional_test"]
    if not shutil.which(argv[0]):
        return False, f"{argv[0]} not found in PATH"
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False, "timed out"
    except OSError as error:
        return False, str(error)
    output = (proc.stdout + proc.stderr).strip()
    if tool.get("functional_test_any_exit"):
        ok = bool(output)
    else:
        ok = proc.returncode == 0
    first = output.splitlines()[0] if output else ""
    return ok, first[:120]


def read_os_release(path="/etc/os-release"):
    info = {}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                key, sep, value = line.strip().partition("=")
                if sep:
                    info[key] = value.strip('"')
    except OSError:
        pass
    return info


def apt_source_files(root="/etc/apt"):
    files = glob.glob(os.path.join(root, "sources.list"))
    files += sorted(glob.glob(os.path.join(root, "sources.list.d", "*.list")))
    files += sorted(glob.glob(os.path.join(root, "sources.list.d", "*.sources")))
    return [f for f in files if os.path.isfile(f)]


def audit_apt_sources(root="/etc/apt"):

    problems = []
    for path in apt_source_files(root):
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        lines = [line.split("#", 1)[0].strip().lower() for line in text.splitlines()]
        entries = re.split(r"\n\s*\n", "\n".join(lines)) if path.endswith(".sources") else lines
        for entry in entries:
            if not entry or re.search(r"(?m)^enabled:\s*no\s*$", entry):
                continue
            if not path.endswith(".sources") and not re.match(r"^deb(?:-src)?\s", entry):
                continue
            if re.search(r"trusted\s*=\s*yes|(?m:^trusted:\s*yes\s*$)", entry):
                problems.append(f"{path}: signature checks disabled (trusted=yes)")
            if "kali.org" in entry or "parrot" in entry:
                problems.append(f"{path}: foreign distribution repository")
            if ("svent" in entry or "apt.zirov.net" in entry) and not re.search(r"signed-by\s*[=:]\s*\S", entry):
                problems.append(f"{path}: Svent source without Signed-By")
    return problems
