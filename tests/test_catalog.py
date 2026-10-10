import copy
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
GROUPS = os.path.join(ROOT, "data", "groups.json")

from svent import catalog, cli, system


def sample_tool(name="nmap", group="network", package=None, exe=None):
    return {
        "schema": 1,
        "name": name,
        "group": group,
        "description": f"{name} description",
        "packaging": "svent",
        "package": package or f"sv-{name}",
        "executables": exe or [name],
        "official_source": "https://example.org",
        "version_policy": "svent-packaged",
        "functional_test": [(exe or [name])[0], "--version"],
    }


def write_fragment(directory, tool):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{tool['name']}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(tool, fh)
    return path


class ShippedGroups(unittest.TestCase):
    def test_shipped_groups_load(self):
        groups = catalog.load_groups(GROUPS)
        self.assertIn("web", groups)
        self.assertEqual(groups["osint"]["name"], "OSINT")

    def test_expected_groups_present(self):
        groups = catalog.load_groups(GROUPS)
        for g in ("recon", "web", "active-directory", "exploitation", "c2"):
            self.assertIn(g, groups)
        self.assertNotIn("sniffing", groups)


class Validation(unittest.TestCase):
    def setUp(self):
        self.groups = {"web": {"name": "Web", "description": ""},
                       "network": {"name": "Network", "description": ""}}
        self.ids = set(self.groups)

    def test_valid_tool(self):
        self.assertEqual(catalog.validate_tool(sample_tool(), self.ids), [])

    def test_malformed_field_types(self):
        for key, value in (("name", None), ("group", []), ("official_source", None),
                           ("executables", "nmap"), ("functional_test", ["nmap", 7])):
            with self.subTest(key=key):
                tool = sample_tool()
                tool[key] = value
                self.assertTrue(catalog.validate_tool(tool, self.ids))

    def test_unsupported_fragment_schema(self):
        tool = sample_tool()
        tool["schema"] = 99
        self.assertTrue(catalog.validate_tool(tool, self.ids))

    def test_rejects_shell_metacharacters(self):
        bad = sample_tool()
        bad["package"] = "nmap; rm -rf /"
        self.assertTrue(catalog.validate_tool(bad, self.ids))

    def test_rejects_plain_http_source(self):
        bad = sample_tool()
        bad["official_source"] = "http://example.org"
        self.assertTrue(catalog.validate_tool(bad, self.ids))

    def test_rejects_test_running_unlisted_binary(self):
        bad = sample_tool()
        bad["functional_test"] = ["sh", "-c", "id"]
        self.assertTrue(catalog.validate_tool(bad, self.ids))

    def test_rejects_unknown_group(self):
        self.assertTrue(catalog.validate_tool(sample_tool(group="nope"), self.ids))

    def test_rejects_missing_field(self):
        bad = sample_tool()
        del bad["executables"]
        self.assertTrue(catalog.validate_tool(bad, self.ids))


class Merge(unittest.TestCase):
    def test_merges_fragments(self):
        with tempfile.TemporaryDirectory() as d:
            write_fragment(d, sample_tool("nmap", "network"))
            write_fragment(d, sample_tool("sqlmap", "web"))
            data = catalog.load(GROUPS, d)
            names = [t["name"] for t in data["tools"]]
            self.assertEqual(names, ["nmap", "sqlmap"])
            self.assertEqual(data["warnings"], [])

    def test_empty_when_no_fragments(self):
        with tempfile.TemporaryDirectory() as d:
            data = catalog.load(GROUPS, d)
            self.assertEqual(data["tools"], [])

    def test_missing_dir_is_empty(self):
        data = catalog.load(GROUPS, "/nonexistent/catalog.d")
        self.assertEqual(data["tools"], [])

    def test_invalid_fragment_skipped_with_warning(self):
        with tempfile.TemporaryDirectory() as d:
            write_fragment(d, sample_tool("nmap", "network"))
            bad = sample_tool("bad", "web")
            bad["official_source"] = "http://x"
            write_fragment(d, bad)
            data = catalog.load(GROUPS, d)
            self.assertEqual([t["name"] for t in data["tools"]], ["nmap"])
            self.assertTrue(data["warnings"])

    def test_conflicting_executable_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            write_fragment(d, sample_tool("nmap", "network", exe=["nmap"]))
            write_fragment(d, sample_tool("other", "network", exe=["nmap"]))
            data = catalog.load(GROUPS, d)
            self.assertEqual(len(data["tools"]), 1)
            self.assertTrue(any("also claimed" in w for w in data["warnings"]))

    def test_malformed_json_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "broken.json"), "w") as fh:
                fh.write("{ not json")
            data = catalog.load(GROUPS, d)
            self.assertEqual(data["tools"], [])
            self.assertTrue(data["warnings"])

    def test_missing_groups_file(self):
        with self.assertRaises(catalog.CatalogError):
            catalog.load_groups("/nonexistent/groups.json")


class AptAudit(unittest.TestCase):
    def test_signed_by_is_checked_per_entry(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "svent.sources", "Types: deb\nURIs: https://apt.zirov.net\nSigned-By: /key.gpg\n\nTypes: deb\nURIs: https://apt.zirov.net\n")
            self.assertEqual(len(system.audit_apt_sources(root)), 1)

    def test_disabled_deb822_is_ignored(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "off.sources", "Types: deb\nURIs: https://apt.zirov.net\nEnabled: no\nTrusted: yes\n")
            self.assertEqual(system.audit_apt_sources(root), [])

    def write(self, root, name, text):
        os.makedirs(os.path.join(root, "sources.list.d"), exist_ok=True)
        with open(os.path.join(root, "sources.list.d", name), "w") as fh:
            fh.write(text)

    def test_flags_trusted_yes(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "x.list", "deb [trusted=yes] http://x testing main\n")
            self.assertTrue(system.audit_apt_sources(root))

    def test_flags_foreign_repository(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "k.list", "deb http://http.kali.org/kali kali-rolling main\n")
            self.assertTrue(system.audit_apt_sources(root))

    def test_flags_svent_without_signed_by(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "z.list", "deb http://repo.svent.invalid rolling main\n")
            self.assertTrue(system.audit_apt_sources(root))

    def test_accepts_signed_deb822(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "svent.sources",
                       "Types: deb\nURIs: http://repo.svent.invalid\nSuites: rolling\n"
                       "Components: main\nSigned-By: /usr/share/keyrings/svent.gpg\n")
            self.assertEqual(system.audit_apt_sources(root), [])

    def test_ignores_commented_trusted(self):
        with tempfile.TemporaryDirectory() as root:
            self.write(root, "d.list", "# deb [trusted=yes] http://x\n")
            self.assertEqual(system.audit_apt_sources(root), [])


class Cli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        write_fragment(self.dir, sample_tool("sqlmap", "web"))
        write_fragment(self.dir, sample_tool("nmap", "network"))
        os.environ["SVENT_GROUPS"] = GROUPS
        os.environ["SVENT_CATALOG_DIR"] = self.dir

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(argv))
        return code, out.getvalue()

    def test_list_group(self):
        code, out = self.run_cli("catalog", "list", "--group", "web")
        self.assertEqual(code, 0)
        self.assertIn("sqlmap", out)
        self.assertNotIn("nmap", out)

    def test_groups_is_table(self):
        code, out = self.run_cli("catalog", "groups")
        self.assertEqual(code, 0)
        self.assertIn("GROUP", out)
        self.assertIn("---", out)

    def test_show_unknown_tool(self):
        code, _ = self.run_cli("catalog", "show", "does-not-exist")
        self.assertEqual(code, 1)

    def test_invalid_catalog_exit_code(self):
        os.environ["SVENT_GROUPS"] = "/nonexistent.json"
        code, _ = self.run_cli("catalog", "groups")
        self.assertEqual(code, 2)
        os.environ["SVENT_GROUPS"] = GROUPS


if __name__ == "__main__":
    unittest.main()
