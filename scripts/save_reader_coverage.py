"""Instrument fmsave: which save entries does a full read actually touch, and which APIs surface them?"""
"""Which save entries does a full fmsave read touch, and which are never opened?

  .venv/bin/python scripts/save_reader_coverage.py SAVE.fm

Patches the section and region readers, calls every public API once, and reports both sets.
"""
import sys
import warnings
import fmsave
import fmsave._container as C
import fmsave._save as S
from fmsave._context import SaveContext

warnings.simplefilter("ignore")
SAVE = sys.argv[1] if len(sys.argv) > 1 else "/Users/kenneth/Library/Application Support/Sports Interactive/Football Manager 27/games/Kenneth  Igbo - Chelsea.fm"

touched = set()
orig_read_section = C.read_section
orig_save_read = S.read_section


def log_section(ci, name):
    touched.add(name)
    return orig_read_section(ci, name)


C.read_section = log_section
S.read_section = log_section

orig_loan = SaveContext._section_loan


def log_loan(self, name):
    touched.add(name)
    return orig_loan(self, name)


SaveContext._section_loan = log_loan

# region-level reads (game_db and other big entries are read as regions)
for fname in ("read_region_frames", "read_chosen_region_frames", "read_region_frame", "read_region_frames_bounded"):
    orig = getattr(C, fname, None)
    if orig is None:
        continue

    def make(fn, tag):
        def wrapper(container_index, *a, **k):
            try:
                name = a[0] if isinstance(a[0], str) else getattr(a[0], "name", None)
                touched.add(str(name))
            except Exception:
                pass
            return fn(container_index, *a, **k)
        return wrapper

    setattr(C, fname, make(orig, fname))

results = {}
with fmsave.open(SAVE) as s:
    entries = sorted(e.name + e.extension for e in s._container_index.entries)
    apis = [m for m in dir(s) if not m.startswith("_") and callable(getattr(s, m))]
    for api in [a for a in apis if a != "close"]:
        try:
            val = getattr(s, api)()
            n = len(val) if hasattr(val, "__len__") else "ok"
            results[api] = f"ok ({n})"
        except TypeError:
            results[api] = "needs args"
        except Exception as e:
            results[api] = f"ERR {str(e)[:60]}"

print("APIs:")
for k in sorted(results):
    print(f"  {k:24} {results[k]}")
print(f"\nentries read: {len(touched)}")
for t in sorted(touched):
    print("  touched:", t)
print("\nentries never read:")
for e in entries:
    base = e.rsplit(".", 1)[0]
    if base not in touched and e not in touched:
        print("  ", e)
