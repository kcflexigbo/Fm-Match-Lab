"""Read *every* entry in an FM27 save, not only the ones fmsave models.

fmsave decodes 13 of the 78 entries. This wrapper opens the rest at the container level: list them,
get their decompressed bytes, their header, and a printable-strings view, and dispatch to structured
decoders where a layout is known.

    from fm27save import SaveReader
    r = SaveReader(path)
    r.sections()                     # every entry: name, type, sizes
    r.raw("shortlist_man")           # decompressed bytes
    r.header("shortlist_man")        # {"version": 0x0103, "type": "tat"}
    r.strings("news", min_len=8)     # printable runs, for narrative entries
    r.decoded("save_game_summary")   # structured where implemented

Every entry begins with the same 6-byte header: u16 version (0x0103), 3-char type, '.'.
"""
from __future__ import annotations

import re
import struct
import warnings
from pathlib import Path

import fmsave

HEADER = struct.Struct("<H3sc")


class SaveReader:
    def __init__(self, path: str | Path):
        self.path = str(path)
        warnings.simplefilter("ignore", category=UserWarning)
        self._save = fmsave.open(self.path)
        self._index = self._save._container_index

    # ---------------------------------------------------------------- container level
    def entries(self):
        return [{"name": e.name, "type": e.extension.lstrip("."),
                 "size": e.decompressed_size, "compressed": e.compressed_size}
                for e in self._index.entries]

    def sections(self):
        names = set(self._index.sections)
        return [e for e in self.entries() if e["name"] in names]

    def raw(self, name: str) -> bytes:
        if name in self._index.sections:
            return self._save._read_section(name)
        for e in self._index.entries:
            if e.name == name or (e.name + e.extension) == name:
                from fmsave import _container as C
                return C.read_directory_entry(self._index, e)
        raise KeyError(f"no entry {name!r}")

    def header(self, name: str):
        head = self.raw(name)[:6]
        if len(head) < 6:
            return None
        version, kind, dot = HEADER.unpack(head)
        return {"version": version, "type": kind.decode("ascii", "replace"), "separator": dot.decode("ascii", "replace")}

    def payload(self, name: str) -> bytes:
        """Bytes after the 6-byte container header."""
        return self.raw(name)[6:]

    def strings(self, name: str, min_len: int = 6, skip_header: bool = True):
        data = self.payload(name) if skip_header else self.raw(name)
        return [m.group().decode("ascii") for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_len, data)]

    def u32s(self, name: str, limit: int = 64):
        data = self.payload(name)
        n = min(limit, len(data) // 4)
        return list(struct.unpack_from("<%dI" % n, data))

    def match_files(self):
        """The per-match files the game keeps inside the save (.scm / .apm)."""
        return [e for e in self.entries() if e["type"] in ("scm", "apm")]

    # ---------------------------------------------------------------- structured decoders
    def decoded(self, name: str):
        fn = getattr(self, "_dec_" + name, None)
        if fn is None:
            return {"name": name, "decoded": False, "header": self.header(name),
                    "note": "raw and strings() available; no structured layout yet"}
        return fn()

    def _dec_save_game_summary(self):
        text = "".join(chr(b) if 32 <= b < 127 else " " for b in self.payload("save_game_summary"))
        return {"decoded": True, "fields": [f.strip() for f in text.split(",") if f.strip()]}

    def _dec_news(self):
        data = self.payload("news")
        text = "".join(chr(b) if 32 <= b < 127 else "\n" for b in data)
        items = [line.strip() for line in text.splitlines() if len(line.strip()) >= 12]
        return {"decoded": True, "count": len(items), "items": items[:200]}

    def _dec_game_info(self):
        return {"decoded": True, "strings": self.strings("game_info", 5)}

    def _dec_memory_pools(self):
        return {"decoded": True, "strings": self.strings("memory_pools", 5)}

    def _dec_fog_of_war(self):
        data = self.payload("fog_of_war")
        return {"decoded": True, "bytes": len(data), "non_zero": sum(1 for b in data if b),
                "u32s": self.u32s("fog_of_war", 8)}

    def __getattr__(self, item):
        """Players, clubs, fixtures, tactics ... fall through to fmsave."""
        if item.startswith("_"):
            raise AttributeError(item)
        return getattr(self._save, item)

    def close(self):
        try:
            self._save.close()
        except Exception:
            pass


def catalog(path):
    r = SaveReader(path)
    try:
        return [{**s, "header": r.header(s["name"])} for s in r.sections()]
    finally:
        r.close()
