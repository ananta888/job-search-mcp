"""Architekturvertrag fuer die oeffentliche Repository-Struktur."""

import os
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RepositoryLayoutTest(unittest.TestCase):
    def test_alte_unterricht_verschachtelung_existiert_nicht(self):
        self.assertFalse(ROOT.joinpath("unterricht").exists())

    def test_src_layout_und_paketmetadaten_existieren(self):
        self.assertTrue(
            ROOT.joinpath("src/job_search_mcp/interfaces/mcp_server.py").is_file()
        )
        pyproject = tomllib.loads(
            ROOT.joinpath("pyproject.toml").read_text(encoding="utf-8")
        )
        self.assertEqual(pyproject["project"]["name"], "job-search-mcp")
        self.assertEqual(
            pyproject["project"]["scripts"]["job-search-mcp"],
            "job_search_mcp.interfaces.mcp_server:main",
        )

    def test_paket_ist_direkt_aus_src_importierbar(self):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-c", "import job_search_mcp"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_opencode_startet_den_installierten_cli_einstieg(self):
        config = ROOT.joinpath(".opencode/opencode.json").read_text(encoding="utf-8")
        self.assertIn("job-search-mcp", config)
        self.assertNotIn("unterricht/unterricht", config)


if __name__ == "__main__":
    unittest.main()
