from __future__ import annotations
import os, shutil, subprocess, tempfile
from pathlib import Path
from jinja2 import Template
from gradianmatch import config
from gradianmatch.resume_model import Resume, resume_to_dict

def render_html(resume: Resume) -> str:
    tmpl = Template((config.DATA_DIR / "cv_template.html.j2").read_text(encoding="utf-8"), autoescape=True)
    return tmpl.render(**resume_to_dict(resume))

def find_chrome() -> str | None:
    candidates = [
        os.environ.get("CHROME_PATH", ""),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        shutil.which("chrome") or "", shutil.which("chromium") or "",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None

def render_pdf(resume: Resume, out_path: str) -> str:
    chrome = find_chrome()
    if chrome is None:
        raise RuntimeError("No Chrome/Edge found for PDF export. Set CHROME_PATH.")
    html = render_html(resume)
    with tempfile.TemporaryDirectory() as td:
        html_path = Path(td) / "cv.html"
        html_path.write_text(html, encoding="utf-8")
        subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-sandbox",
                        f"--print-to-pdf={out_path}", "--no-pdf-header-footer",
                        html_path.as_uri()], check=True, capture_output=True, timeout=60)
    return out_path
