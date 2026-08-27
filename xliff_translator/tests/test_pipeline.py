from pathlib import Path
from lxml import etree
from xliff_translator.pipeline import translate_file
from xliff_translator.core import parse_xliff, iter_units, source_element, qname, XLIFF_NS

FIXTURE = Path(__file__).parent / "fixture.xlf"

class FakeTranslator:
    def translate_batch(self, texts, source_lang, target_lang):
        out = []
        for text in texts:
            if "⟦XLSEG:" in text:
                import re
                out.append(re.sub(r"⟦XLSEG:(\d+)⟧(.*?)⟦XLSEG:\1⟧", lambda m: f"⟦XLSEG:{m.group(1)}⟧ FR {m.group(1)} ⟦XLSEG:{m.group(1)}⟧", text, flags=re.S))
            else:
                out.append("FR " + text)
        return out

def test_full_pipeline_preserves_xliff_structure(tmp_path):
    out_paths = translate_file(FIXTURE, tmp_path, ["fr"], FakeTranslator())
    assert len(out_paths) == 1
    original = parse_xliff(FIXTURE)
    translated = parse_xliff(out_paths[0])
    orig_units = list(iter_units(original))
    trans_units = list(iter_units(translated))
    assert len(orig_units) == len(trans_units) == 56
    for a, b in zip(orig_units, trans_units):
        assert a.get("id") == b.get("id")
        assert etree.tostring(source_element(a)) == etree.tostring(source_element(b))
        target = b.find(qname(XLIFF_NS, "target"))
        assert target is not None
        # Same structure/attributes as source; only text differs.
        def sig(e):
            return [(n.tag, tuple(sorted(n.attrib.items()))) for n in e.iter()]
        sa = sig(source_element(a))
        st = sig(target)
        st[0] = (qname(XLIFF_NS, "source"), st[0][1])
        assert sa == st
