from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = ["README.md", "LIVE_DEMO_CHECKLIST.md", "customers.json", "recovery.py", "assistant.py", "server.py",
         "demo.py", "tests/test_recovery.py", "run.ps1", "package.json", "package-lock.json", "package_submission.py",
         "web/index.html", "web/style.css", "web/app.js", "web/vapi-entry.js", "web/dist/vapi.js",
         "demo-output.txt", "verification.txt", "rehearsal-proof.png"]

if __name__ == "__main__":
    missing = [name for name in FILES if not (ROOT / name).is_file()]
    if missing:
        raise SystemExit("Missing files: " + ", ".join(missing))
    with zipfile.ZipFile(ROOT / "voice-submission.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / name, "cedar-voice-agent/" + name)
    print("Packaged source, browser bundle and rehearsal evidence; live voice demo remains unverified.")
