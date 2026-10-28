import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
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
                         [uri, f"--dir={dest}", "--seed-time=0",
                          "--bt-save-metadata=true"])
        self.assertEqual(len(result.stdout.splitlines()), 1)
        seeded = self.run_command("sh", "-c", "exec " + result.stdout)
        self.assertEqual(seeded.returncode, 0, seeded.stderr)
        self.assertEqual(json.loads(capture.read_text()),
                         [uri, f"--dir={dest}", "--seed-ratio=0.0",
                          "--check-integrity=true", "--bt-load-saved-metadata=true"])

    def test_serializer_rejects_line_breaks(self):
        for value in ["a\nb", "a\rb"]:
            result = self.run_command(str(self.bin / "pierdat-command"), "echo", value)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")

    def backend(self, body):
        for path in self.bin.glob("pierdat-check-*"):
            path.unlink()
        self.script(self.bin / "pierdat-check-test", "#!/bin/sh\nexit 0\n")
        self.script(self.bin / "pierdat-get-test", body)

    def test_failed_backend_does_not_change_config(self):
        self.backend("#!/bin/sh\necho unintended-command\nexit 1\n")
        self.config.write_text("# existing\n")
        result = self.run_command(str(self.bin / "pierdat"), "test://x", "/data")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.config.read_text(), "# existing\n")

    def test_backend_uses_its_shebang(self):
        self.backend('#!/usr/bin/python3\nprint("seed-command")\n')
        result = self.run_command(str(self.bin / "pierdat"), "test://x", "/data")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.config.read_text(), "seed-command\n")

    def wait_for(self, predicate, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(0.05)
        self.fail("Timed out waiting for child state")

    def start_daemon(self):
        process = subprocess.Popen([str(self.bin / "pierdatd")], env=self.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        def cleanup():
            if process.poll() is None:
                process.terminate()
            try:
                process.communicate(timeout=9)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
        self.addCleanup(cleanup)
        return process

    def test_shutdown_kills_stubborn_seeder_group(self):
        pidfile = self.work / "pids"
        child = self.script(self.work / "stubborn", "#!/usr/bin/python3\n"
                            "import os, signal, subprocess, time\n"
                            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                            "child = subprocess.Popen(['sleep', '60'])\n"
                            f"open({str(pidfile)!r}, 'w').write(str(os.getpid()) + ' ' + str(child.pid))\n"
                            "while True: time.sleep(1)\n")
        self.config.write_text(str(child) + "\n")
        daemon = self.start_daemon()
        self.wait_for(lambda: pidfile.exists() and len(pidfile.read_text().split()) == 2)
        pids = [int(pid) for pid in pidfile.read_text().split()]
        def cleanup_group():
            try:
                os.killpg(pids[0], signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.addCleanup(cleanup_group)
        daemon.terminate()
        stdout, stderr = daemon.communicate(timeout=9)
        self.assertEqual(daemon.returncode, 0, stdout + stderr)
        for pid in pids:
            stat = Path(f"/proc/{pid}/stat")
            self.assertTrue(not stat.exists() or stat.read_text().split()[2] == "Z",
                            f"Seeder process {pid} survived shutdown")

    def test_failed_seeder_restarts_without_restarting_healthy_seeder(self):
        attempts = self.work / "attempts"
        healthy_starts = self.work / "healthy"
        failing = self.script(self.work / "failing", "#!/bin/sh\n"
                              f"echo attempt >> '{attempts}'\nexit 1\n")
        healthy = self.script(self.work / "healthy-seed", "#!/bin/sh\n"
                              f"echo start >> '{healthy_starts}'\nexec sleep 60\n")
        self.config.write_text(f"{failing}\n{healthy}\n")
        daemon = self.start_daemon()
        self.wait_for(lambda: attempts.exists() and len(attempts.read_text().splitlines()) >= 2)
        self.assertIsNone(daemon.poll())
        self.assertEqual(healthy_starts.read_text(), "start\n")
        daemon.terminate()
        daemon.communicate(timeout=9)
        count = attempts.read_text()
        time.sleep(0.1)
        self.assertEqual(attempts.read_text(), count)


if __name__ == "__main__":
    unittest.main()
