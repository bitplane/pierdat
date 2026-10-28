import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]


class PierdatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pierdat-test-")
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.root = self.work / "root"
        shutil.copytree(SOURCE / "root", self.root)
        self.bin = self.root / "usr/bin"
        self.config = self.root / "etc/pier.dat"
        self.config.write_text("")
        self.mocks = self.work / "mocks"
        self.mocks.mkdir()
        self.env = dict(os.environ, PATH=f"{self.mocks}:{os.environ['PATH']}")

    def script(self, path, body):
        path.write_text(body)
        path.chmod(0o755)
        return path

    def run_command(self, *args):
        return subprocess.run(args, env=self.env, text=True,
                              capture_output=True, timeout=10)

    def test_aria_arguments_round_trip(self):
        import json
        capture = self.work / "args.json"
        self.script(self.mocks / "aria2c", "#!/usr/bin/python3\n"
                    "import json, sys\n"
                    f"open({str(capture)!r}, 'w').write(json.dumps(sys.argv[1:]))\n")
        uri = "magnet:?xt=urn:btih:example&dn=hello"
        dest = str(self.work / "space ' quote * $(touch BAD) \\n literal")
        result = self.run_command(str(self.bin / "pierdat-get-aria2c"), uri, dest)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(capture.read_text()),
                         [uri, f"--dir={dest}", "--seed-time=0"])
        self.assertEqual(len(result.stdout.splitlines()), 1)
        seeded = self.run_command("sh", "-c", "exec " + result.stdout)
        self.assertEqual(seeded.returncode, 0, seeded.stderr)
        self.assertEqual(json.loads(capture.read_text()),
                         [uri, f"--dir={dest}", "--seed-ratio=0.0",
                          "--check-integrity=true"])

    def test_serializer_rejects_line_breaks(self):
        for value in ["a\nb", "a\rb"]:
            result = self.run_command(str(self.bin / "pierdat-command"), "echo", value)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
