"""Editor toolbar: hand-drawn SVG icons + data-driven button layout.

Every icon is drawn on a 24x24 grid with the same stroke style, so the
set looks like one family and never depends on a device's emoji font.
"""
import html as _html

# inner SVG markup only; the wrapper adds viewBox and stroke styling
ICONS = {
    "panid": '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4"/><path d="M10 12h5M10 16h5"/>',
    "ulo": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 9.5h18"/><path d="M6.5 7.3h4"/>',
    "texto": '<path d="M5 6.5h14" stroke-width="3.2"/><path d="M5 11.5h14M5 15.5h14M5 19.5h9"/>',
    "subtexto": '<path d="M5 7h9" stroke-width="2.4"/><path d="M5 12h14M5 16h14M5 20h8"/>',
    "butangan": '<path d="M13 4v16M17 4v16"/><path d="M17 4h-6.5a4 4 0 0 0 0 8H13"/>',
    "pagpindutan": '<rect x="3" y="5.5" width="15" height="9" rx="2.5"/><path d="M14 12l7 3-3 1.2 1.8 3.3-1.6.9-1.8-3.3L14 19z" fill="currentColor" stroke-width="1.2"/>',
    "silpo": '<path d="M10 14a4 4 0 0 0 5.6 0l3-3a4 4 0 0 0-5.6-5.6l-1 1"/><path d="M14 10a4 4 0 0 0-5.6 0l-3 3a4 4 0 0 0 5.6 5.6l1-1"/>',
    "ladawan": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M4 18l5-5 4 4 3-3 4 4"/>',
    "bidyo": '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M10 9.5v5l4.5-2.5z" fill="currentColor"/>',
    "ladawanan": '<rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/><rect x="13" y="13" width="8" height="8" rx="1.5"/>',
    "garrapon": '<rect x="6" y="3" width="12" height="3" rx="1"/><path d="M7 6v1.5C5.5 8.5 5 9.5 5 11v7a3 3 0 0 0 3 3h8a3 3 0 0 0 3-3v-7c0-1.5-.5-2.5-2-3.5V6"/>',
    "estilo": '<path d="M9 4C7 4 6.5 5 6.5 6.5v2c0 1.2-.7 2.5-2.5 3.5 1.8 1 2.5 2.3 2.5 3.5v2C6.5 19 7 20 9 20"/><path d="M15 4c2 0 2.5 1 2.5 2.5v2c0 1.2.7 2.5 2.5 3.5-1.8 1-2.5 2.3-2.5 3.5v2c0 1.5-.5 2.5-2.5 2.5"/>',
    "tengnga": '<path d="M4 6h16M7 12h10M5 18h14"/>',
    "toggle": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>',
    "immuna": '<path d="M3 6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4.5H3z" fill="currentColor" fill-opacity=".35" stroke="none"/><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10.5h18"/>',
    "udi": '<path d="M3 13.5h18V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" fill="currentColor" fill-opacity=".35" stroke="none"/><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 13.5h18"/>',
    "pagtudo": '<rect x="3" y="8" width="18" height="8" rx="4"/><circle cx="8" cy="12" r="1.3" fill="currentColor" stroke="none"/><path d="M12 12h5"/>',
    "baga": '<path d="M12 4.2 21 19.5H3z"/><path d="M12 10v4.3"/><circle cx="12" cy="16.9" r=".8" fill="currentColor" stroke="none"/>',
    "sao": '<path d="M4.5 18v-4.2c0-3 1.6-5.4 4.6-6.8l.9 1.4c-1.6.9-2.4 2-2.5 3.6H10V18z" fill="currentColor"/><path d="M14 18v-4.2c0-3 1.6-5.4 4.6-6.8l.9 1.4c-1.6.9-2.4 2-2.5 3.6H19.5V18z" fill="currentColor"/>',
    "pila": '<path d="M4 6.5h16M4 17.5h16" opacity=".45"/><path d="M8 12h8" stroke-width="2.6"/>',
    "banag": '<circle cx="5.5" cy="7" r="1.4" fill="currentColor" stroke="none"/><circle cx="5.5" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="5.5" cy="17" r="1.4" fill="currentColor" stroke="none"/><path d="M10 7h10M10 12h10M10 17h10"/>',
    "bilang": '<path d="M4.4 4.6l1.5-.8v4.6"/><path d="M4 10.4c.3-.9 2.5-1 2.8.1.2 1-2.7 2-2.8 3.1H7"/><path d="M4 16.3h2.6l-1.3 1.5c1.1-.1 1.9.6 1.7 1.5-.3 1-2.1 1.1-2.9.3"/><path d="M10.5 6.2h9.5M10.5 12h9.5M10.5 18h9.5"/>',
    "naaramid": '<path d="M3.5 7l1.7 1.7L8.3 5.4M3.5 12.6l1.7 1.7 3.1-3.3M3.5 18.2l1.7 1.7 3.1-3.3"/><path d="M11.5 7h8.5M11.5 12.6h8.5M11.5 18.2h8.5"/>',
    "duakolum": '<rect x="3" y="4" width="8" height="16" rx="1.5"/><rect x="13" y="4" width="8" height="16" rx="1.5"/>',
    "dalan": '<rect x="3" y="7" width="18" height="10" rx="2"/><path d="M6.5 12h3M11 12h3M15.5 12h2"/>',
    "pagimbagan": '<rect x="4" y="3.5" width="16" height="17" rx="2.5"/><path d="M12 7.2l1.2 2.5 2.7.4-2 1.9.5 2.7-2.4-1.3-2.4 1.3.5-2.7-2-1.9 2.7-.4z"/><path d="M8 17.5h8"/>',
    "listaan": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18M3 14.5h18M10 10v9"/>',
    "ayab": '<path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v9a1.5 1.5 0 0 1-1.5 1.5H10l-4.5 4v-4H5.5A1.5 1.5 0 0 1 4 14.5z"/><path d="M8 9h8M8 12h5"/>',
    "saludsod": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.6 2.2c-.7.4-1.1 1-1.1 1.8"/><circle cx="12" cy="17" r=".9" fill="currentColor" stroke="none"/>',
    "pagbilangan": '<circle cx="12" cy="13.5" r="7.5"/><path d="M12 9.5v4l2.5 1.5"/><path d="M9.5 3h5"/>',
    "pagsuratan": '<path d="M3 4.5h6" opacity=".55"/><rect x="3" y="8" width="18" height="10" rx="2"/><path d="M7.5 11v4" stroke-width="2"/>',
    "no": '<path d="M12 3.5 20.5 12 12 20.5 3.5 12z"/><path d="M8.7 12l2.3 2.3 4.3-4.6"/>',
    "isuble": '<path d="M4 12a8 8 0 0 1 13.5-5.8"/><path d="M20 12a8 8 0 0 1-13.5 5.8"/><path d="M17.5 3v3.5H14"/><path d="M6.5 21v-3.5H10"/>',
    "kolor": '<path d="M12 3.5s6 6 6 10.5a6 6 0 0 1-12 0C6 9.5 12 3.5 12 3.5z" fill="currentColor" fill-opacity=".25"/><path d="M9.3 14.6a2.7 2.7 0 0 0 2.7 2.7"/>',
    "teksto-kolor": '<path d="M6 15.5 12 3.5l6 12M8.3 11.5h7.4"/><path d="M5 20h14" stroke-width="3.2"/>',
    "gen-theme": '<path d="M11 3l1.8 5.2L18 10l-5.2 1.8L11 17l-1.8-5.2L4 10l5.2-1.8z"/><path d="M19 15v5M16.5 17.5h5"/>',
    "gen-pattern": '<rect x="3" y="3" width="18" height="18" rx="2" opacity=".45"/><path d="M3 7.5A4.5 4.5 0 0 0 7.5 3M12 7.5A4.5 4.5 0 0 0 7.5 12M16.5 3A4.5 4.5 0 0 0 21 7.5M12 7.5A4.5 4.5 0 0 1 16.5 12M7.5 12A4.5 4.5 0 0 0 12 16.5M3 16.5A4.5 4.5 0 0 1 7.5 21M12 16.5A4.5 4.5 0 0 0 16.5 12M21 16.5A4.5 4.5 0 0 0 16.5 21"/>',
    "gen-pattern-card": '<rect x="3" y="3" width="18" height="18" rx="2.5"/><rect x="7" y="7" width="10" height="10" rx="1.5" stroke-dasharray="2 2"/>',
    "undo": '<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
    "redo": '<path d="m15 14 5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/>',
    "chevron": '<path d="m6 9 6 6 6-6"/>',
    "save": '<path d="M5 3h11l3 3v15H5z"/><path d="M8 3v5h7V3"/><rect x="8" y="13" width="8" height="8"/>',
}


def icon_svg(key):
    return (
        '<svg class="ico" viewBox="0 0 24 24" width="22" height="22" fill="none" '
        'stroke="currentColor" stroke-width="1.7" stroke-linecap="round" '
        'stroke-linejoin="round" aria-hidden="true" focusable="false">'
        + ICONS[key] + "</svg>"
    )


def _q(s):
    return _html.escape(s, quote=True)


def _snip(icon, label, cmd, prefix, placeholder, suffix, tip=None):
    return dict(icon=icon, label=label, cmd=cmd, kind="snippet",
                data=dict(prefix=prefix, placeholder=placeholder, suffix=suffix), tip=tip)


def _block(icon, label, cmd, open_, body="", select=""):
    d = dict(open=open_, close="murdong")
    if body:
        d["body"] = body
    if select:
        d["select"] = select
    return dict(icon=icon, label=label, cmd=cmd, kind="block", data=d)


def _line(icon, label, cmd, line):
    return dict(icon=icon, label=label, cmd=cmd, kind="line", data=dict(line=line))


# Groups, in reading order. Labels reuse the editor's existing Ilokano
# names; `cmd` is the real Pintas command shown in the tooltip.
GROUPS = [
    [  # page
        _snip("panid", "Panid", "panid", 'panid "', "Titulo ti Website", '"'),
        _snip("ulo", "Ulo", "ulo", 'ulo "', "Titulo ti Panid", '"'),
    ],
    [  # text
        _snip("texto", "Dakkel a Ulo", "texto", 'texto "', "Ballaigi ti ulo daytoy", '"'),
        _snip("subtexto", "Bassit nga Ulo", "subtexto", 'subtexto "', "Bassit nga sao", '"'),
        _snip("butangan", "Parapo", "butangan", 'butangan "', "Isuratmo ditoy ti sao mo.", '"'),
        _snip("sao", "Sao", "sao", 'sao "', "Isuratmo ditoy ti sao", '" "Ti nagsao"'),
        _snip("baga", "Baga", "baga", 'baga "', "Napateg a damag", '"'),
        _snip("pagtudo", "Pagtudo", "pagtudo", 'pagtudo "', "Baro!", '"'),
    ],
    [  # lists
        _snip("banag", "Banag", "banag", 'banag "', "Baro a banag", '"'),
        _snip("bilang", "Bilang", "bilang", 'bilang "', "Sumaruno a hakbang", '"'),
        _snip("naaramid", "Naaramid", "naaramid", 'naaramid "', "Naaramid a banag", '"'),
    ],
    [  # media & links
        _snip("silpo", "Silpo", "silpo", 'silpo "', "Ti nagan ti silpo", '" "https://example.com"'),
        _snip("ladawan", "Ladawan", "ladawan", 'ladawan "', "ladawan.jpg", '"'),
        _block("ladawanan", "Ladawanan", "ladawanan", "ladawanan"),
        _snip("bidyo", "Bidyo", "bidyo", 'bidyo "', "https://youtu.be/aqz-KE-bpKQ", '"'),
    ],
    [  # layout
        _block("immuna", "Immuna", "immuna", "immuna"),
        _block("dalan", "Dalan", "dalan", "dalan"),
        _block("garrapon", "Lalaem", "garrapon", "garrapon"),
        _block("duakolum", "Dua a Kolum", "duakolum", "duakolum"),
        _block("udi", "Udi", "udi", "udi"),
        _line("pila", "Pila", "pila", "pila"),
        _line("tengnga", "Itengnga", "tengnga", "tengnga"),
    ],
    [  # ready-made pieces
        _snip("pagimbagan", "Pagimbagan", "pagimbagan", 'pagimbagan "', "Nagan ti pagimbagan",
              '" "Iti daytoy a card ket isuratmo ti detalye."'),
        _line("listaan", "Listaan", "listaan",
              'listaan\nringgor "Plano" "Presyo"\nringgor "Basic" "Libre"'),
        _snip("ayab", "Ayab", "ayab", 'ayab "', "Ayabandakami", '" "mailto:hello@example.com"'),
        _snip("saludsod", "Saludsod", "saludsod", 'saludsod "', "Saludsod", '" "Sungbat"'),
        _snip("pagbilangan", "Pagbilangan", "pagbilangan", 'pagbilangan "', "2026-12-31T23:59:59",
              '" "Dandani"'),
        _snip("pagsuratan", "Pagsuratan", "pagsuratan", 'pagsuratan "', "Naganmo", '" "Isurat ditoy"'),
    ],
    [  # interactive & logic
        dict(icon="toggle", label="Ipakita/Ilemmeng", cmd="pagpindutan + garrapon",
             kind="toggle", data={}, id="toggle-btn"),
        _snip("pagpindutan", "Buton", "pagpindutan", 'pagpindutan "', "I-click daytoy", '"'),
        _block("no", "No", "no", "no 5 > 3", body='butangan "Daytoy ket makita."', select="5 > 3"),
        _block("isuble", "Isuble", "isuble", "isuble i manipud 1 agingga 3",
               body='butangan "Numero {{i}}"', select="1 agingga 3"),
    ],
    [  # style
        _snip("kolor", "Kolor", "kolor", 'kolor "', "lightblue", '"'),
        _snip("teksto-kolor", "Teksto-kolor", "teksto-kolor", 'teksto-kolor "', "#1f2937", '"'),
        _block("estilo", "Estilo", "estilo", "estilo"),
    ],
]

GENERATORS = [
    dict(icon="gen-theme", label="Baro a Tema", id="gen-theme-btn",
         tip="Mangaramid iti baro a tema (kolor + font)"),
    dict(icon="gen-pattern", label="Pattern", id="gen-pattern-btn",
         tip="Kusikus-style a pattern iti panid"),
    dict(icon="gen-pattern-card", label="Pattern ti Lalaem", id="gen-pattern-card-btn",
         tip="Kusikus-style a pattern iti lalaem"),
]


def _button(t):
    attrs = ['class="tb"', 'type="button"']
    if t.get("id"):
        attrs.append(f'id="{t["id"]}"')
    kind = t.get("kind")
    if kind:
        attrs.append(f'data-kind="{kind}"')
        for k, v in t["data"].items():
            attrs.append(f'data-{k}="{_q(v)}"')
    tip = t.get("tip") or (
        t["label"] if t.get("cmd") in (None, t["label"].lower()) else f'{t["label"]} ({t["cmd"]})'
    )
    attrs.append(f'title="{_q(tip)}"')
    attrs.append(f'aria-label="{_q(t["label"])}"')
    return (f'<button {" ".join(attrs)}>{icon_svg(t["icon"])}'
            f'<span class="lbl">{_html.escape(t["label"]).replace("/", "/<wbr>")}</span></button>')


# Only these stay on the always-visible row; everything else lives in the
# collapsible "Ad-adu" (more) panel, so the top of the editor stays calm.
ESSENTIAL = {
    "panid", "texto", "butangan", "silpo", "ladawan", "immuna", "garrapon",
    "duakolum", "pagimbagan", "ayab", "estilo",
}
# Panel captions, one per entry of GROUPS (same order).
SECTION_NAMES = [
    "Page", "Text", "Lists", "Media & links", "Layout", "Ready-made",
    "Interactive & logic", "Style",
]


def _section(name, inner, row_attrs=""):
    return (f'<div class="sec"><div class="sec-name">{_html.escape(name)}</div>'
            f'<div class="row"{row_attrs}>{inner}</div></div>')


def build_toolbar_html():
    main = []
    for group in GROUPS:
        keep = [t for t in group if t["icon"] in ESSENTIAL]
        if keep:
            main.append('<div class="group">' + "".join(_button(t) for t in keep) + "</div>")
    main.append(
        '<button type="button" class="more-btn" id="more-toggle" aria-expanded="false" '
        'aria-controls="more-panel" title="Ipakita/Ilemmeng dagiti ad-adu a block">'
        + icon_svg("chevron") + "<span>Ad-adu</span></button>"
    )
    sections = []
    for name, group in zip(SECTION_NAMES, GROUPS):
        rest = [t for t in group if t["icon"] not in ESSENTIAL]
        if rest:
            sections.append(_section(name, "".join(_button(t) for t in rest)))
    sections.append(_section("Themes", "", ' id="theme-group" title="tema"'))
    sections.append(_section("Generators", "".join(_button(t) for t in GENERATORS)))
    return (
        '<div class="tb-main">\n    ' + "\n    ".join(main) + "\n  </div>\n"
        '  <div id="more-panel" hidden>\n    ' + "\n    ".join(sections) + "\n  </div>"
    )


TOOLBAR_CSS = """
  .toolbar { background: #111827; border-top: 1px solid #374151; }
  .toolbar[hidden], #more-panel[hidden] { display: none; }
  .tb-main { display: flex; flex-wrap: wrap; gap: 0.35rem 0.5rem; align-items: center;
    padding: 0.4rem 0.8rem; }
  #more-panel { display: flex; flex-wrap: wrap; gap: 0.5rem 0.9rem; padding: 0.5rem 0.8rem 0.6rem;
    border-top: 1px solid #374151; max-height: 40vh; overflow-y: auto; background: #0f172a; }
  .sec { display: flex; flex-direction: column; gap: 0.15rem; padding-right: 0.9rem;
    border-right: 1px solid #1f2937; }
  .sec:last-child { border-right: none; }
  .sec-name { font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.08em;
    color: #9ca3af; padding-left: 0.3rem; }
  .sec .row { display: flex; flex-wrap: wrap; gap: 0.15rem; align-items: center; min-height: 1.6rem; }
  .collapse-btn, .more-btn { display: inline-flex; align-items: center; gap: 0.35rem;
    background: transparent; color: #d1d5db; border: 1px solid #4b5563; border-radius: 999px;
    padding: 0.25rem 0.75rem; font: inherit; font-size: 0.78rem; cursor: pointer; }
  .collapse-btn:hover, .more-btn:hover { background: #374151; }
  .collapse-btn:focus-visible, .more-btn:focus-visible { outline: 2px solid #60a5fa; outline-offset: 1px; }
  .collapse-btn .ico, .more-btn .ico { width: 14px; height: 14px; transition: transform 0.15s; }
  .collapse-btn[aria-expanded="false"] .ico { transform: rotate(-90deg); }
  .more-btn[aria-expanded="true"] .ico { transform: rotate(180deg); }
  .more-btn { margin-left: 0.2rem; }
  .group { display: flex; gap: 0.15rem; padding: 0 0.5rem 0 0;
    border-right: 1px solid #374151; align-items: center; }
  .group:last-child { border-right: none; }
  button.tb { display: flex; flex-direction: column; align-items: center; justify-content: flex-start;
    gap: 0.2rem; width: 4.5rem; min-height: 3.1rem; padding: 0.35rem 0.1rem 0.25rem;
    background: transparent; color: #e5e7eb; border: 1px solid transparent; border-radius: 8px;
    font: inherit; cursor: pointer; }
  button.tb:hover { background: #374151; border-color: #4b5563; }
  button.tb:active { transform: translateY(1px); }
  button.tb:focus-visible { outline: 2px solid #60a5fa; outline-offset: 1px; }
  button.tb .ico { flex: none; color: #93c5fd; }
  button.tb .lbl { font-size: 0.62rem; line-height: 1.1; text-align: center; color: #d1d5db;
    max-width: 100%; overflow-wrap: break-word; }
  button.swatch { width: 26px; height: 26px; border-radius: 50%; border: 2px solid #fff;
    cursor: pointer; padding: 0; margin: 0 0.1rem; }
  #save-btn { flex-direction: row; gap: 0.4rem; width: auto; min-height: 0; margin-left: 0.4rem;
    padding: 0.4rem 0.8rem; background: #2563eb; border-color: #2563eb; }
  #save-btn .ico { color: #fff; width: 18px; height: 18px; }
  #save-btn .lbl { font-size: 0.85rem; font-weight: 600; color: #fff; }
  #save-btn:hover { background: #1d4ed8; }
  button.hdr { flex-direction: row; gap: 0.35rem; width: auto; min-height: 0;
    padding: 0.35rem 0.65rem; border-color: #4b5563; }
  button.hdr .ico { width: 18px; height: 18px; color: #e5e7eb; }
  button.hdr .lbl { font-size: 0.8rem; color: #e5e7eb; }
  button.hdr:disabled { opacity: 0.35; cursor: default; }
  button.hdr:disabled:hover { background: transparent; border-color: #4b5563; }
  #undo-btn { margin-left: auto; }
  @media (max-width: 900px) {
    .tb-main { flex-wrap: nowrap; overflow-x: auto; -webkit-overflow-scrolling: touch; }
    .group, .more-btn { flex: none; }
  }
"""
