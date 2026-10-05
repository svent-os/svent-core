"""Command-line interface for Svent OS."""

import argparse
import json
import sys

from . import __version__, catalog, system


def render_table(headers, rows):
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    header = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    sep = "  ".join("-" * widths[i] for i in range(len(headers)))
    lines = [header, sep]
    for row in rows:
        lines.append("  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row)))
    return "\n".join(lines)


def cmd_catalog_list(args, data):
    tools = catalog.by_group(data, args.group) if args.group else data["tools"]
    if args.json:
        print(json.dumps(tools, indent=2))
        return 0
    if not tools:
        print("no tools in catalog")
        return 0
    rows = [[t["name"], t["group"], t["description"]] for t in tools]
    print(render_table(["NAME", "GROUP", "DESCRIPTION"], rows))
    return 0


def cmd_catalog_show(args, data):
    tool = catalog.find(data, args.name)
    if not tool:
        print(f"svent: unknown tool: {args.name}", file=sys.stderr)
        return 1
    installed = system.installed_version(tool["package"])
    rows = [
        ["Name", tool["name"]],
        ["Group", tool["group"]],
        ["Description", tool["description"]],
        ["Package", f"{tool['package']} ({tool['packaging']})"],
        ["Executables", ", ".join(tool["executables"])],
        ["Official site", tool["official_source"]],
        ["Version policy", tool["version_policy"]],
        ["Installed", installed or "no"],
    ]
    if tool.get("known_limitations"):
        rows.append(["Limitations", tool["known_limitations"]])
    print(render_table(["FIELD", "VALUE"], rows))
    return 0


def cmd_catalog_groups(args, data):
    rows = []
    for group, meta in data["groups"].items():
        rows.append([group, len(catalog.by_group(data, group)), meta["description"]])
    print(render_table(["GROUP", "TOOLS", "DESCRIPTION"], rows))
    return 0


def cmd_tools_status(args, data):
    rows = []
    for tool in data["tools"]:
        rows.append({"name": tool["name"], "package": tool["package"],
                     "installed": system.installed_version(tool["package"])})
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("no tools in catalog")
        return 0
    table = [[r["name"], r["package"], r["installed"] or "-"] for r in rows]
    print(render_table(["NAME", "PACKAGE", "INSTALLED"], table))
    return 0


def cmd_tools_test(args, data):
    tools = [catalog.find(data, n) for n in args.names] if args.names else [
        t for t in data["tools"] if system.installed_version(t["package"])]
    if not tools:
        print("No catalog tools are installed.")
        return 0
    rows = []
    failures = 0
    for name, tool in zip(args.names or [t["name"] for t in tools], tools):
        if tool is None:
            rows.append(["FAIL", name, "unknown tool"])
            failures += 1
            continue
        ok, detail = system.run_functional_test(tool)
        rows.append(["PASS" if ok else "FAIL", tool["name"], detail])
        failures += 0 if ok else 1
    print(render_table(["RESULT", "TOOL", "DETAIL"], rows))
    return 1 if failures else 0


def cmd_doctor(args, data):
    problems = 0
    osr = system.read_os_release()
    print(f"[info] OS: {osr.get('PRETTY_NAME', 'unknown')}")
    if osr.get("ID") != "svent" and "debian" not in osr.get("ID_LIKE", "") \
            and osr.get("ID") != "debian":
        print("[warn] not a Debian-based system; package checks may be incomplete")
    print(f"[ok]   catalog valid: {len(data['tools'])} tools")
    for warning in data.get("warnings", []):
        print(f"[warn] catalog: {warning}")
    for issue in system.audit_apt_sources():
        print(f"[fail] {issue}")
        problems += 1
    if not problems:
        print("[ok]   APT sources: no unsafe entries found")
    return 1 if problems else 0


def build_parser():
    parser = argparse.ArgumentParser(prog="svent", description="Svent OS system tool")
    parser.add_argument("--version", action="version", version=f"svent {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    cat = sub.add_parser("catalog", help="browse the supported tool catalog")
    catsub = cat.add_subparsers(dest="action", required=True)
    p = catsub.add_parser("list", help="list catalog tools")
    p.add_argument("--group")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_catalog_list)
    p = catsub.add_parser("show", help="show one tool")
    p.add_argument("name")
    p.set_defaults(func=cmd_catalog_show)
    p = catsub.add_parser("groups", help="list tool groups")
    p.set_defaults(func=cmd_catalog_groups)

    tools = sub.add_parser("tools", help="inspect installed catalog tools")
    toolsub = tools.add_subparsers(dest="action", required=True)
    p = toolsub.add_parser("status", help="show installed versions")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_tools_status)
    p = toolsub.add_parser("test", help="run functional tests")
    p.add_argument("names", nargs="*")
    p.set_defaults(func=cmd_tools_test)

    p = sub.add_parser("doctor", help="check system health")
    p.set_defaults(func=cmd_doctor)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        data = catalog.load()
    except catalog.CatalogError as exc:
        print(f"svent: {exc}", file=sys.stderr)
        return 2
    return args.func(args, data)
