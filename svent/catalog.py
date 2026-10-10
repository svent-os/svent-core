import glob
import json
import os
import re

GROUPS_PATH = "/usr/share/svent/groups.json"
CATALOG_DIR = "/usr/share/svent/catalog.d"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9+.-]*$")
REQUIRED = ("name", "group", "description", "packaging", "package",
            "executables", "official_source", "version_policy",
            "functional_test")
POLICIES = {"follow-debian-testing", "svent-packaged", "pinned"}
PACKAGING = {"debian", "svent"}


class CatalogError(Exception):
    pass


def groups_path():
    return os.environ.get("SVENT_GROUPS", GROUPS_PATH)


def catalog_dir():
    return os.environ.get("SVENT_CATALOG_DIR", CATALOG_DIR)


def load_groups(path=None):
    path = path or groups_path()
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        raise CatalogError(f"groups file not found: {path}")
    except json.JSONDecodeError as exc:
        raise CatalogError(f"groups file is not valid JSON: {exc}")
    if not isinstance(raw, dict) or raw.get("schema") != 1 \
            or not isinstance(raw.get("groups"), dict):
        raise CatalogError("groups file has unsupported or missing schema")
    groups = {}
    for gid, meta in raw["groups"].items():
        if not NAME_RE.match(gid):
            raise CatalogError(f"invalid group id: {gid}")
        if isinstance(meta, str):
            groups[gid] = {"name": gid, "description": meta}
        elif isinstance(meta, dict):
            if not isinstance(meta.get("name", gid), str) or not isinstance(meta.get("description", ""), str):
                raise CatalogError(f"invalid group definition: {gid}")
            groups[gid] = {"name": meta.get("name", gid),
                           "description": meta.get("description", "")}
        else:
            raise CatalogError(f"invalid group definition: {gid}")
    return groups


def validate_tool(tool, group_ids):
    if not isinstance(tool, dict):
        return ["not a JSON object"]
    missing = [k for k in REQUIRED if k not in tool]
    if missing:
        return [f"missing {', '.join(missing)}"]
    errors = []
    for key in ("name", "group", "description", "packaging", "package", "official_source", "version_policy"):
        if not isinstance(tool[key], str) or not tool[key].strip():
            errors.append(f"{key} must be a non-empty string")
    for key in ("executables", "functional_test"):
        if not isinstance(tool[key], list) or not tool[key] or not all(isinstance(value, str) and value for value in tool[key]):
            errors.append(f"{key} must be a non-empty string list")
    if errors:
        return errors
    if tool.get("schema", 1) != 1:
        errors.append("unsupported schema version")
    if not NAME_RE.match(tool["name"]) or not NAME_RE.match(tool["package"]):
        errors.append("invalid name or package")
    if tool["group"] not in group_ids:
        errors.append(f"unknown group {tool['group']}")
    if tool["packaging"] not in PACKAGING:
        errors.append(f"unknown packaging {tool['packaging']}")
    if tool["version_policy"] not in POLICIES:
        errors.append("unknown version policy")
    if not tool["official_source"].startswith("https://"):
        errors.append("official_source must use https")
    desktop_file = tool.get("desktop_file")
    if desktop_file is not None and (not isinstance(desktop_file, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9+._-]*\.desktop", desktop_file)):
        errors.append("desktop_file must be a desktop filename")
    exes = tool["executables"]
    if not exes or not all(isinstance(e, str) and NAME_RE.match(e) for e in exes):
        errors.append("invalid executables")
    test = tool["functional_test"]
    if not test or test[0] not in exes:
        errors.append("functional_test must run a listed executable")
    return errors


def validate(data):
    if not isinstance(data, dict) or data.get("schema") != 1:
        return ["unsupported or missing schema version"]
    if not isinstance(data.get("groups", {}), dict) or not isinstance(data.get("tools", []), list):
        return ["groups must be an object and tools must be a list"]
    group_ids = set(data.get("groups", {}))
    errors = []
    seen = set()
    owners = {}
    for i, tool in enumerate(data.get("tools", [])):
        tool_errors = validate_tool(tool, group_ids)
        name = tool.get("name", f"[{i}]") if isinstance(tool, dict) else f"[{i}]"
        if tool_errors:
            errors.extend(f"tool {name}: {e}" for e in tool_errors)
            continue
        if name in seen:
            errors.append(f"tool {name}: duplicate name")
        seen.add(name)
        for exe in tool["executables"]:
            if exe in owners and owners[exe] != tool["package"]:
                errors.append(f"tool {name}: executable {exe} also claimed by {owners[exe]}")
            owners[exe] = tool["package"]
    return errors


def load_fragments(directory, groups):
    directory = directory or catalog_dir()
    group_ids = set(groups)
    tools = []
    warnings = []
    seen = set()
    owners = {}
    if not os.path.isdir(directory):
        return tools, warnings
    for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        try:
            with open(path, encoding="utf-8") as fh:
                tool = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"{path}: not valid JSON: {exc}")
            continue
        tool_errors = validate_tool(tool, group_ids)
        if tool_errors:
            warnings.append(f"{path}: {'; '.join(tool_errors)}")
            continue
        if tool["name"] in seen:
            warnings.append(f"{path}: duplicate tool name {tool['name']}")
            continue
        conflict = next((exe for exe in tool["executables"]
                         if exe in owners and owners[exe] != tool["package"]), None)
        if conflict:
            warnings.append(f"{path}: executable {conflict} also claimed by {owners[conflict]}")
            continue
        for exe in tool["executables"]:
            owners[exe] = tool["package"]
        seen.add(tool["name"])
        tools.append(tool)
    tools.sort(key=lambda t: (t["group"], t["name"]))
    return tools, warnings


def load(groups_file=None, fragments_dir=None):
    groups = load_groups(groups_file)
    tools, warnings = load_fragments(fragments_dir, groups)
    return {"schema": 1, "groups": groups, "tools": tools, "warnings": warnings}


def find(data, name):
    for tool in data["tools"]:
        if tool["name"] == name:
            return tool
    return None


def by_group(data, group):
    return [t for t in data["tools"] if t["group"] == group]
