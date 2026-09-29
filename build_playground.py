"""Build the static Pintas Playground for GitHub Pages.

    python build_playground.py          # writes docs/

GitHub Pages can only serve static files, so there is no Python server.
Instead the page loads Pyodide (Python compiled to WebAssembly) in the
visitor's browser and runs the REAL compiler there, so the playground can
never drift from `pintas.py`. It reuses the local editor's own page
(toolbar, highlighting, generators) and only swaps the network layer.

Re-run this whenever pintas.py, theme_generator.py, pattern_generator.py or
editor_toolbar.py change, then commit docs/.
"""
import json
import shutil
from pathlib import Path

import pintas_editor

PYODIDE_VERSION = "0.26.4"
PY_FILES = ["pintas.py", "pintas_editor.py", "theme_generator.py", "pattern_generator.py", "editor_toolbar.py"]

# Replaces the local server: routes the editor's fetch() calls to Pyodide.
SHIM = r"""<script src="https://cdn.jsdelivr.net/pyodide/v__PYODIDE__/full/pyodide.js"></script>
<script>
(function () {
  var status = document.getElementById("save-status");
  var realFetch = window.fetch.bind(window);
  var FILES = __PY_FILES__;
  var PY_API = [
    "import json, sys",
    "sys.path.insert(0, '/pintas')",
    "import pintas, pintas_editor",
    "def api(path, payload_json):",
    "    p = json.loads(payload_json)",
    "    try:",
    "        if path == '/compile':",
    "            html, _ = pintas.compile_pintas(p.get('source', ''), live_reload=False)",
    "            return json.dumps({'ok': True, 'html': html})",
    "        if path == '/generate-theme':",
    "            snippet, accent, bg = pintas_editor.generate_theme_snippet(p.get('seed'))",
    "            return json.dumps({'ok': True, 'snippet': snippet, 'accent': accent, 'bg': bg})",
    "        if path == '/generate-pattern':",
    "            snippet = pintas_editor.generate_pattern_snippet(p.get('seed'), p.get('size', 6),",
    "                p.get('accent', '#2563eb'), p.get('bg', '#f0f6ff'), p.get('target', 'body'))",
    "            return json.dumps({'ok': True, 'snippet': snippet})",
    "        return json.dumps({'ok': False, 'error': 'Unknown endpoint ' + path})",
    "    except Exception as e:",
    "        return json.dumps({'ok': False, 'error': str(e) or type(e).__name__})"
  ].join("\n");

  var ready = (async function () {
    status.textContent = "Agkarga ti Python...";
    var py = await loadPyodide();
    py.FS.mkdirTree("/pintas");
    for (var i = 0; i < FILES.length; i++) {
      var res = await realFetch("py/" + FILES[i]);
      if (!res.ok) throw new Error("Saan a naikarga ti " + FILES[i]);
      py.FS.writeFile("/pintas/" + FILES[i], await res.text());
    }
    py.runPython(PY_API);
    status.textContent = "";
    return py.globals.get("api");
  })();
  ready.catch(function (e) { status.textContent = "Diak nakarga ti Python: " + e.message; });

  function reply(obj) {
    return { ok: true, json: function () { return Promise.resolve(obj); } };
  }

  window.fetch = function (url, opts) {
    var path = String(url);
    if (path === "/save") {           // no server file: download it instead
      var src = JSON.parse(opts.body).source;
      var a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([src], { type: "text/plain;charset=utf-8" }));
      a.download = "panid.pintas";
      document.body.appendChild(a); a.click(); a.remove();
      return Promise.resolve(reply({ ok: true }));
    }
    if (path.charAt(0) !== "/") return realFetch(url, opts);
    return ready.then(function (api) {
      return reply(JSON.parse(api(path, opts.body)));
    });
  };
})();
</script>
"""


def build(out_dir=Path("docs")):
    out_dir = Path(out_dir)
    py_dir = out_dir / "py"
    py_dir.mkdir(parents=True, exist_ok=True)
    for name in PY_FILES:
        shutil.copyfile(name, py_dir / name)

    starter = Path("hello.pintas").read_text(encoding="utf-8")
    page = pintas_editor.render_editor_html(Path("hello.pintas"))
    assert starter in json.loads(
        page.split('id="initial-source">', 1)[1].split("</script>", 1)[0].replace("<\\/", "</")
    ), "starter source was not embedded"

    old = 'preview.src = "/index.html?t=" + Date.now();'
    assert old in page, "editor template changed: update build_playground.py"
    page = page.replace(old, "preview.srcdoc = data.html;")
    page = page.replace("<title>Pintas Editor</title>", "<title>Pintas Playground</title>")
    page = page.replace("<h1>Pintas Editor</h1>", "<h1>Pintas Playground</h1>")

    shim = SHIM.replace("__PYODIDE__", PYODIDE_VERSION).replace("__PY_FILES__", json.dumps(PY_FILES))
    marker = '<script type="application/json" id="initial-source">'
    assert marker in page
    page = page.replace(marker, shim + marker, 1)

    (out_dir / "index.html").write_text(page, encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    return out_dir


if __name__ == "__main__":
    print("Built", build(), "- now commit docs/ and enable GitHub Pages (main branch, /docs folder).")
