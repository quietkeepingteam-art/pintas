"""The Pintas browser editor: toolbar, syntax highlighting, live preview.

Kept apart from the compiler (`pintas.py`) so the compiler stays small and
has no web-UI code in it. Start it with `python pintas.py site.pintas --editor`
or by importing `run_editor` from here. This module only *uses* the compiler;
the compiler never imports it except when `--editor` is requested.
"""
import functools
import http.server
import json
import random
import re
import threading
import time
import webbrowser
from pathlib import Path

from pintas import (
    CONTAINER_KINDS,
    LIST_KINDS,
    THEMES,
    _serve_with_handler,
    compile_pintas,
    copy_local_images,
    root_rule_from_theme,
)


def json_safe(s):
    """Prevent embedded JSON from prematurely closing a <script> tag,
    same reasoning and fix as css_safe() for <style>."""
    return s.replace("</", "<\\/")


HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _mix_hex(a, b, weight_a):
    """Blend two #rrggbb colors; weight_a is how much of `a` to keep."""
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(
        f"{round(x * weight_a + y * (1 - weight_a)):02x}" for x, y in zip(ca, cb)
    )


def generate_theme_snippet(seed):
    """Ask theme_generator.py for a contrast-verified palette and return
    Pintas source for it, plus the colors the pattern button reuses.

    A generated palette has no registered `tema` name, so the snippet
    applies the shipped theme that owns the same Google Fonts (so the
    fonts actually load) and then overrides every variable with `estilo`.
    Works with the compiler as-is - no new syntax.
    """
    import theme_generator as tg  # lazy: the generators import pintas

    rng = random.Random(seed)
    palette = None
    for _ in range(200):
        candidate = tg.generate_palette(rng)
        if all(tg.verify_palette(candidate).values()):
            palette = candidate
            break
    if palette is None:
        raise ValueError("Awan ti nagballigi a palette. Padasem manen.")

    donor = next(
        (n for n, t in THEMES.items() if t["font-url"] == palette["font-url"]),
        "puraw",
    )
    snippet = (
        "# >>> tema-generator\n"
        f'tema "{donor}"\n'
        "estilo\n"
        f"{root_rule_from_theme(palette)}\n"
        "murdong\n"
        "# <<< tema-generator"
    )
    return snippet, palette["accent"], palette["bg"]


def generate_pattern_snippet(seed, size, accent, bg, target):
    """Ask pattern_generator.py for a kusikus-style tile and return an
    `estilo` block for the page (`body`) or containers (`.garrapon`)."""
    import pattern_generator as pg

    if not (HEX_COLOR.match(accent) and HEX_COLOR.match(bg)):
        raise ValueError("Sayop a kolor.")
    if target not in ("body", ".garrapon"):
        raise ValueError("Sayop a target.")
    size = max(2, min(12, int(size)))
    line = _mix_hex(accent, bg, 0.22)  # subtle, so text stays readable on top
    svg, unit = pg.generate_pattern_svg(seed, size, line, bg)
    label = "pattern-generator" + ("-lalaem" if target == ".garrapon" else "")
    return (
        f"# >>> {label}\n"
        + pg.estilo_snippet(svg, unit, target)
        + f"\n# <<< {label}"
    )


# Words the editor's syntax highlighter recognises, by role. Built from the
# compiler's own tables where they exist so new containers/lists light up
# automatically; the rest are the fixed single-line commands.
EDITOR_KEYWORDS = {
    "block": sorted(CONTAINER_KINDS) + ["estilo"],
    "end": ["murdong"],
    "ctrl": ["no", "isuble"],
    "cmd": sorted(set(LIST_KINDS) | {
        "panid", "ulo", "texto", "subtexto", "butangan", "sao", "baga",
        "pagtudo", "pagpindutan", "silpo", "ladawan", "bidyo", "pagimbagan",
        "listaan", "ringgor", "ayab", "saludsod", "pagbilangan", "pagsuratan",
        "pila", "tengnga", "kolor", "teksto-kolor", "tema",
    }),
}


# The editor's own UI chrome - deliberately plain and system-fonted,
# so the *tool* works offline even though a chosen `tema` still needs
# the internet for its Google Fonts inside the preview pane.
EDITOR_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ilo">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pintas Editor</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
      Helvetica, Arial, sans-serif;
    display: flex; flex-direction: column; background: #f3f4f6;
  }
  header {
    display: flex; flex-wrap: wrap; gap: 0.6rem; align-items: center;
    padding: 0.6rem 0.8rem; background: #1f2937; color: #fff;
  }
  header h1 { font-size: 0.95rem; margin: 0 0.4rem 0 0; font-weight: 600; }
__TOOLBAR_CSS__
  #save-status { font-size: 0.8rem; color: #a7f3d0; min-width: 6rem; }
  main { flex: 1; display: flex; min-height: 0; }
  #editor-wrap { position: relative; flex: 1 1 50%; min-width: 0; background: #fff;
    border-right: 1px solid #d1d5db; }
  #preview-pane { flex: 1 1 50%; min-width: 0; }
  /* The textarea and the highlight <pre> must share identical metrics so the
     coloured text sits exactly under the (transparent) typed text. */
  #editor, #hl {
    position: absolute; inset: 0; margin: 0; border: none; padding: 1rem;
    font-size: 0.9rem; line-height: 1.5; tab-size: 4;
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    white-space: pre-wrap; overflow-wrap: break-word; word-break: normal;
    overflow-x: hidden; overflow-y: scroll; letter-spacing: 0;
  }
  #editor { resize: none; background: transparent; color: transparent;
    caret-color: #111827; outline: none; z-index: 1; }
  #editor::selection { background: rgba(37, 99, 235, 0.25); color: transparent; }
  #hl { z-index: 0; pointer-events: none; color: #111827; background: #fff;
    scrollbar-color: transparent transparent; }
  #hl::-webkit-scrollbar { background: transparent; }
  #hl::-webkit-scrollbar-thumb { background: transparent; }
  #hl code { font: inherit; }
  .t-cmd { color: #1d4ed8; font-weight: 600; }
  .t-block, .t-end { color: #7c3aed; font-weight: 600; }
  .t-ctrl { color: #c2410c; font-weight: 600; }
  .t-str { color: #15803d; }
  .t-var { color: #b45309; background: #fef3c7; border-radius: 3px; }
  .t-num { color: #0e7490; }
  .t-op { color: #be185d; }
  .t-kw { color: #c2410c; }
  .t-com { color: #6b7280; font-style: italic; }
  .t-prop { color: #0369a1; }
  .t-css { color: #374151; }
  .t-err { color: #b91c1c; text-decoration: underline wavy #ef4444; }
  #preview-pane { display: flex; flex-direction: column; }
  #error-box {
    display: none; background: #fef2f2; color: #991b1b; padding: 0.6rem 1rem;
    font-size: 0.85rem; border-bottom: 1px solid #fecaca; white-space: pre-wrap;
  }
  #preview { flex: 1; border: none; background: #fff; }
</style>
</head>
<body>
<header>
  <h1>Pintas Editor</h1>
  <button type="button" class="collapse-btn" id="toolbar-toggle" aria-expanded="true" aria-controls="toolbar" title="Ilemmeng/Ipakita ti toolbar">__CHEVRON_ICON__<span>Toolbar</span></button>
  <button class="tb hdr" type="button" id="undo-btn" title="Undo (Ctrl+Z)" aria-label="Undo" disabled>__UNDO_ICON__<span class="lbl">Undo</span></button>
  <button class="tb hdr" type="button" id="redo-btn" title="Redo (Ctrl+Y)" aria-label="Redo" disabled>__REDO_ICON__<span class="lbl">Redo</span></button>
  <button class="tb" type="button" id="save-btn" title="I-save (write to the file)" aria-label="I-save">__SAVE_ICON__<span class="lbl">I-save</span></button>
  <span id="save-status"></span>
</header>
<nav class="toolbar" id="toolbar" aria-label="Pintas toolbar">
    __TOOLBAR_HTML__
</nav>
<main>
  <div id="editor-wrap">
    <pre id="hl" aria-hidden="true"><code></code></pre>
    <textarea id="editor" spellcheck="false" autocapitalize="off" autocomplete="off" autocorrect="off"></textarea>
  </div>
  <div id="preview-pane">
    <div id="error-box"></div>
    <iframe id="preview" title="Preview"></iframe>
  </div>
</main>
<script type="application/json" id="initial-source">__INITIAL_SOURCE_JSON__</script>
<script>
(function () {
  var THEMES = [
    ["puraw", "#2563eb"], ["nangisit", "#3b82f6"], ["asul", "#2563eb"],
    ["berde", "#16a34a"], ["duyaw", "#d97706"], ["labaga", "#dc2626"],
    ["rabii", "#e838ff"], ["balitok", "#d4af37"], ["danum", "#0891b2"]
  ];
  var themeGroup = document.getElementById("theme-group");
  THEMES.forEach(function (pair) {
    var b = document.createElement("button");
    b.className = "swatch";
    b.style.background = pair[1];
    b.title = pair[0];
    b.dataset.kind = "line";
    b.dataset.line = 'tema "' + pair[0] + '"';
    themeGroup.appendChild(b);
  });

  var editor = document.getElementById("editor");
  var preview = document.getElementById("preview");
  var errorBox = document.getElementById("error-box");
  var saveBtn = document.getElementById("save-btn");
  var saveStatus = document.getElementById("save-status");

  function insertAtCursor(text) {
    var start = editor.selectionStart;
    var end = editor.selectionEnd;
    editor.value = editor.value.slice(0, start) + text + editor.value.slice(end);
    return start;
  }

  function insertSnippet(prefix, placeholder, suffix) {
    var insertStart = insertAtCursor(prefix + placeholder + suffix + "\\n");
    var selStart = insertStart + prefix.length;
    var selEnd = selStart + placeholder.length;
    editor.focus();
    editor.setSelectionRange(selStart, selEnd);
    commit();
  }

  function insertBlock(openLine, closeLine, body, select) {
    body = body || "";
    var snippet = openLine + "\\n" + body + "\\n" + closeLine + "\\n";
    var insertStart = insertAtCursor(snippet);
    var at = select ? openLine.indexOf(select) : -1;
    editor.focus();
    if (at >= 0) {
      editor.setSelectionRange(insertStart + at, insertStart + at + select.length);
    } else {
      var caret = insertStart + openLine.length + 1;
      editor.setSelectionRange(caret, caret);
    }
    commit();
  }

  function insertLine(text) {
    var insertStart = insertAtCursor(text + "\\n");
    var caret = insertStart + text.length + 1;
    editor.focus();
    editor.setSelectionRange(caret, caret);
    commit();
  }

  var toggleCounter = 1;
  function insertToggle() {
    var name = "detalye" + toggleCounter++;
    var before = 'pagpindutan "Ipakita/Ilemmeng" "' + name + '"\\n\\n'
      + 'garrapon "' + name + '"\\n';
    var after = "\\nmurdong\\n";
    var insertStart = insertAtCursor(before + after);
    var caret = insertStart + before.length;
    editor.focus();
    editor.setSelectionRange(caret, caret);
    commit();
  }
  document.getElementById("toggle-btn").addEventListener("click", insertToggle);

  document.querySelectorAll('button[data-kind="snippet"]').forEach(function (btn) {
    btn.addEventListener("click", function () {
      insertSnippet(btn.dataset.prefix, btn.dataset.placeholder, btn.dataset.suffix);
    });
  });
  document.querySelectorAll('button[data-kind="block"]').forEach(function (btn) {
    btn.addEventListener("click", function () {
      insertBlock(btn.dataset.open, btn.dataset.close, btn.dataset.body, btn.dataset.select);
    });
  });
  document.querySelectorAll('button[data-kind="line"]').forEach(function (btn) {
    btn.addEventListener("click", function () {
      insertLine(btn.dataset.line);
    });
  });

  // Generators: each click asks the server for a fresh, verified result and
  // REPLACES the previous generated block (marked by "# >>> name" ...
  // "# <<< name" comment lines) instead of stacking copies.
  var lastColors = { accent: "#2563eb", bg: "#f0f6ff" };

  function placeGenerated(name, snippet) {
    var re = new RegExp("# >>> " + name + "\\n[\\\\s\\\\S]*?# <<< " + name + "\\n?");
    if (re.test(editor.value)) {
      editor.value = editor.value.replace(re, function () { return snippet + "\\n"; });
      editor.focus();
      commit();
    } else {
      insertLine(snippet);
    }
  }

  function generate(url, body, name, done) {
    body.seed = Math.floor(Math.random() * 1000000);
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!data.ok) {
          errorBox.textContent = data.error;
          errorBox.style.display = "block";
          return;
        }
        if (done) done(data);
        placeGenerated(name, data.snippet);
      })
      .catch(function () {
        errorBox.textContent = "Saan a maka-konekta iti server.";
        errorBox.style.display = "block";
      });
  }

  document.getElementById("gen-theme-btn").addEventListener("click", function () {
    generate("/generate-theme", {}, "tema-generator", function (data) {
      lastColors = { accent: data.accent, bg: data.bg };
    });
  });
  document.getElementById("gen-pattern-btn").addEventListener("click", function () {
    generate("/generate-pattern",
      { size: 6, accent: lastColors.accent, bg: lastColors.bg, target: "body" },
      "pattern-generator");
  });
  document.getElementById("gen-pattern-card-btn").addEventListener("click", function () {
    generate("/generate-pattern",
      { size: 4, accent: lastColors.accent, bg: lastColors.bg, target: ".garrapon" },
      "pattern-generator-lalaem");
  });

  // ---- Syntax highlighting -------------------------------------------
  var KW = __KEYWORDS_JSON__;
  var ROLE = {};
  Object.keys(KW).forEach(function (role) {
    KW[role].forEach(function (w) { ROLE[w] = role; });
  });
  var WORD_KW = { manipud: 1, agingga: 1, addang: 1, pudno: 1, saan: 1 };
  var hl = document.getElementById("hl");
  var hlCode = hl.querySelector("code");

  function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function span(cls, s) { return '<span class="t-' + cls + '">' + esc(s) + "</span>"; }

  function strHtml(s) {
    var out = "", last = 0, m, re = /\\{\\{[^}]*\\}\\}/g;
    while ((m = re.exec(s))) {
      out += esc(s.slice(last, m.index)) + span("var", m[0]);
      last = m.index + m[0].length;
    }
    return out + esc(s.slice(last));
  }

  function restHtml(rest) {
    var re = /("[^"]*"?)|(\\{\\{[^}]*\\}\\})|(-?\\d+(?:\\.\\d+)?)|([A-Za-z_][A-Za-z0-9_-]*)|(==|!=|>=|<=|>|<)/g;
    var out = "", last = 0, m;
    while ((m = re.exec(rest))) {
      out += esc(rest.slice(last, m.index));
      if (m[1] !== undefined) {
        var closed = m[1].length > 1 && m[1].charAt(m[1].length - 1) === '"';
        out += closed ? '<span class="t-str">' + strHtml(m[1]) + "</span>" : span("err", m[1]);
      } else if (m[2] !== undefined) out += span("var", m[2]);
      else if (m[3] !== undefined) out += span("num", m[3]);
      else if (m[4] !== undefined) out += WORD_KW[m[4]] ? span("kw", m[4]) : esc(m[4]);
      else out += span("op", m[5]);
      last = m.index + m[0].length;
    }
    return out + esc(rest.slice(last));
  }

  function lineHtml(line, st) {
    var t = line.trim();
    if (st.css) {                         // inside estilo: opaque CSS
      if (t === "murdong") { st.css = false; return span("end", line); }
      var pm = /^(\\s*)([A-Za-z-]+)(\\s*:)(.*)$/.exec(line);
      if (pm) return esc(pm[1]) + span("prop", pm[2]) + esc(pm[3]) + span("css", pm[4]);
      return span("css", line);
    }
    if (t === "") return esc(line);
    if (t.charAt(0) === "#" || t.slice(0, 2) === "//") return span("com", line);
    var m = /^(\\s*)(\\S+)(.*)$/.exec(line);
    var role = Object.prototype.hasOwnProperty.call(ROLE, m[2]) ? ROLE[m[2]] : null;
    if (m[2] === "estilo") st.css = true;
    return esc(m[1]) + span(role || "err", m[2]) + restHtml(m[3]);
  }

  function highlight() {
    var st = { css: false };
    var html = editor.value.split("\\n").map(function (l) { return lineHtml(l, st); }).join("\\n");
    // trailing newline so the last (empty) line keeps its height in the <pre>
    hlCode.innerHTML = html + "\\n";
    hl.scrollTop = editor.scrollTop;
    hl.scrollLeft = editor.scrollLeft;
  }
  editor.addEventListener("scroll", function () {
    hl.scrollTop = editor.scrollTop;
    hl.scrollLeft = editor.scrollLeft;
  });

  var debounceTimer = null;
  function scheduleCompile() {
    highlight();
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(compileNow, 400);
  }

  function compileNow() {
    fetch("/compile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: editor.value })
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.ok) {
          errorBox.style.display = "none";
          preview.src = "/index.html?t=" + Date.now();
        } else {
          errorBox.textContent = data.error;
          errorBox.style.display = "block";
        }
      })
      .catch(function () {
        errorBox.textContent = "Saan a maka-konekta iti server.";
        errorBox.style.display = "block";
      });
  }

  saveBtn.addEventListener("click", function () {
    saveStatus.textContent = "Agser-serve...";
    fetch("/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: editor.value })
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        saveStatus.textContent = data.ok ? "Naisalbar!" : ("Sayop: " + data.error);
      })
      .catch(function () {
        saveStatus.textContent = "Saan a maka-konekta iti server.";
      })
      .finally(function () {
        setTimeout(function () { saveStatus.textContent = ""; }, 2500);
      });
  });

  // ---- Undo / redo ---------------------------------------------------
  // A textarea's own undo stack is wiped whenever a script sets .value, and
  // every toolbar button and generator does. So we keep our own history.
  var undoBtn = document.getElementById("undo-btn");
  var redoBtn = document.getElementById("redo-btn");
  var hist = [], hIdx = -1, typingTop = false, lastTyped = 0, burstStart = 0, HMAX = 300;

  function updateUndoUi() {
    undoBtn.disabled = hIdx <= 0;
    redoBtn.disabled = hIdx >= hist.length - 1;
  }

  function record(kind) {
    var cur = editor.value;
    if (hIdx >= 0 && hist[hIdx] === cur) return;
    var now = Date.now();
    if (kind === "type" && typingTop && now - lastTyped < 700 && now - burstStart < 5000) {
      hist[hIdx] = cur;                    // same burst of typing = one undo step
    } else {
      hist.length = hIdx + 1;              // a new edit ends the redo branch
      hist.push(cur);
      if (hist.length > HMAX) hist.shift();
      hIdx = hist.length - 1;
      if (kind === "type") burstStart = now;
    }
    typingTop = kind === "type";
    lastTyped = now;
    updateUndoUi();
  }

  function commit() {
    record("edit");
    scheduleCompile();
  }

  function restore(target) {
    var from = editor.value, to = hist[target];
    // put the caret at the end of whatever changed
    var p = 0, max = Math.min(from.length, to.length);
    while (p < max && from.charAt(p) === to.charAt(p)) p++;
    var q = 0;
    while (q < max - p && from.charAt(from.length - 1 - q) === to.charAt(to.length - 1 - q)) q++;
    var top = editor.scrollTop;
    editor.value = to;
    editor.focus();
    editor.setSelectionRange(to.length - q, to.length - q);
    editor.scrollTop = top;
    hIdx = target;
    typingTop = false;
    updateUndoUi();
    scheduleCompile();
  }

  function undo() { if (hIdx > 0) restore(hIdx - 1); }
  function redo() { if (hIdx < hist.length - 1) restore(hIdx + 1); }

  undoBtn.addEventListener("click", undo);
  redoBtn.addEventListener("click", redo);
  editor.addEventListener("keydown", function (e) {
    if (!(e.ctrlKey || e.metaKey) || e.altKey) return;
    var k = e.key.toLowerCase();
    if (k === "z" && !e.shiftKey) { e.preventDefault(); undo(); }
    else if (k === "y" || (k === "z" && e.shiftKey)) { e.preventDefault(); redo(); }
  });
  editor.addEventListener("beforeinput", function (e) {
    if (e.inputType === "historyUndo") { e.preventDefault(); undo(); }
    else if (e.inputType === "historyRedo") { e.preventDefault(); redo(); }
  });
  editor.addEventListener("input", function () { record("type"); scheduleCompile(); });

  // ---- Collapsible toolbar; the choice is remembered ------------------
  var toolbarEl = document.getElementById("toolbar");
  var toolbarToggle = document.getElementById("toolbar-toggle");
  var moreBtn = document.getElementById("more-toggle");
  var morePanel = document.getElementById("more-panel");
  function remember(key, on) { try { localStorage.setItem(key, on ? "1" : "0"); } catch (e) {} }
  function recall(key) { try { return localStorage.getItem(key); } catch (e) { return null; } }
  function showToolbar(on) {
    toolbarEl.hidden = !on;
    toolbarToggle.setAttribute("aria-expanded", String(on));
  }
  function showMore(on) {
    morePanel.hidden = !on;
    moreBtn.setAttribute("aria-expanded", String(on));
  }
  toolbarToggle.addEventListener("click", function () {
    showToolbar(toolbarEl.hidden);
    remember("pintas.toolbar", !toolbarEl.hidden);
  });
  moreBtn.addEventListener("click", function () {
    showMore(morePanel.hidden);
    remember("pintas.more", !morePanel.hidden);
  });
  showToolbar(recall("pintas.toolbar") !== "0");
  showMore(recall("pintas.more") === "1");

  editor.value = JSON.parse(document.getElementById("initial-source").textContent);
  record("edit");
  highlight();
  compileNow();
})();
</script>
</body>
</html>"""


def render_editor_html(source_path):
    """Read the current file fresh each time, so a manual refresh in the
    browser reflects edits made outside the editor too."""
    try:
        current = source_path.read_text(encoding="utf-8")
    except OSError:
        current = ""
    embedded = json_safe(json.dumps(current))
    import editor_toolbar as tb  # lazy, like the generators: only the editor needs it

    page = EDITOR_HTML_TEMPLATE.replace("__TOOLBAR_CSS__", tb.TOOLBAR_CSS)
    page = page.replace("__TOOLBAR_HTML__", tb.build_toolbar_html())
    page = page.replace("__SAVE_ICON__", tb.icon_svg("save"))
    page = page.replace("__UNDO_ICON__", tb.icon_svg("undo"))
    page = page.replace("__REDO_ICON__", tb.icon_svg("redo"))
    page = page.replace("__CHEVRON_ICON__", tb.icon_svg("chevron"))
    page = page.replace("__KEYWORDS_JSON__", json_safe(json.dumps(EDITOR_KEYWORDS)))
    # The user's source goes in last so nothing inside it can be mistaken
    # for one of the placeholders above.
    return page.replace("__INITIAL_SOURCE_JSON__", embedded)


class EditorHandler(http.server.SimpleHTTPRequestHandler):
    """Serves the editor UI at "/", the live-compiled preview (and its
    copied images) as ordinary static files from `directory`, and two
    POST endpoints the editor's JS talks to: /compile and /save.
    """

    def __init__(self, *args, source_path=None, image_dir=None, **kwargs):
        self.source_path = source_path
        self.image_dir = image_dir
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            body = render_editor_html(self.source_path).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"ok": False, "error": "Sayop a JSON"})
            return

        if self.path == "/compile":
            source = payload.get("source", "")
            try:
                result, local_images = compile_pintas(source, live_reload=False)
                out_dir = Path(self.directory)
                (out_dir / "index.html").write_text(result, encoding="utf-8")
                copy_local_images(local_images, self.image_dir, out_dir)
                self._send_json(200, {"ok": True})
            except SyntaxError as e:
                self._send_json(200, {"ok": False, "error": str(e)})
        elif self.path == "/generate-theme":
            try:
                snippet, accent, bg = generate_theme_snippet(payload.get("seed"))
                self._send_json(200, {"ok": True, "snippet": snippet,
                                      "accent": accent, "bg": bg})
            except (ValueError, ImportError) as e:
                self._send_json(200, {"ok": False, "error": str(e)})
        elif self.path == "/generate-pattern":
            try:
                snippet = generate_pattern_snippet(
                    payload.get("seed"), payload.get("size", 6),
                    payload.get("accent", "#2563eb"), payload.get("bg", "#f0f6ff"),
                    payload.get("target", "body"),
                )
                self._send_json(200, {"ok": True, "snippet": snippet})
            except (ValueError, TypeError, ImportError) as e:
                self._send_json(200, {"ok": False, "error": str(e)})
        elif self.path == "/save":
            source = payload.get("source", "")
            try:
                self.source_path.write_text(source, encoding="utf-8")
                self._send_json(200, {"ok": True})
            except OSError as e:
                self._send_json(200, {"ok": False, "error": str(e)})
        else:
            self._send_json(404, {"ok": False, "error": "Awan ti mabirukan"})

    def _send_json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # keep the console quiet; the editor doesn't need per-request logs


def start_editor_server(source_path, preview_dir, port):
    preview_dir.mkdir(parents=True, exist_ok=True)
    handler = functools.partial(
        EditorHandler,
        directory=str(preview_dir),
        source_path=source_path,
        image_dir=source_path.parent,
    )
    return _serve_with_handler(handler, port)


def run_editor(source_path, output_path, port):
    if not source_path.exists():
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            'panid "Umuna a Website"\n'
            'ulo "Umuna a Panid"\n\n'
            'texto "Naragsak nga Aldaw!"\n\n'
            'tema "asul"\n',
            encoding="utf-8",
        )

    served_port = start_editor_server(source_path, output_path.parent, port)
    url = f"http://localhost:{served_port}/"
    print(f"Agserserbi ti editor iti {url} (Ctrl+C tapno agsardeng)")
    threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nNagsardeng.")
