#!/usr/bin/env python3
"""Genera assets/lang/<idioma>.txt a partir de tools/i18n/<idioma>_escenas.tsv.

El .tsv tiene el texto inglés del juego y su traducción; no se publica. El resultado sólo guarda un
hash de cada frase inglesa y la traducción, así el repositorio no contiene texto del juego.

Uso:
  python3 tools/make_translation.py es                      # genera assets/lang/es.txt
  python3 tools/make_translation.py es --disc juego.cue     # además comprueba que no falte nada
  python3 tools/make_translation.py --dump juego.cue        # lista las frases inglesas del disco
"""
import argparse
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
MAX_LEN = 40  # más o menos lo que cabe en una línea de subtítulo (320 píxeles)


def fnv1a(data: bytes) -> int:
    h = 0x811C9DC5
    for b in data:
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


def key(text: str) -> int:
    # Misma normalización que el launcher (game_lang.cpp): sin espacios a los extremos.
    return fnv1a(text.strip().encode("latin-1"))


# --- Lectura del disco: imagen BIN (MODE2/2352) → sistema de archivos ISO → DATA.VOL ---------
def read_bin_path(path):
    if path.lower().endswith(".cue"):
        with open(path, encoding="latin-1") as f:
            m = re.search(r'FILE\s+"([^"]+)"', f.read())
        path = os.path.join(os.path.dirname(path), m.group(1))
    return path


class Disc:
    def __init__(self, path):
        self.f = open(read_bin_path(path), "rb")

    def sector(self, lba):
        self.f.seek(lba * 2352 + 24)
        return self.f.read(2048)

    def read(self, lba, size):
        out = bytearray()
        while len(out) < size:
            out += self.sector(lba)
            lba += 1
        return bytes(out[:size])

    def find(self, path):
        pvd = self.sector(16)
        lba, size = struct.unpack_from("<I", pvd, 156 + 2)[0], struct.unpack_from("<I", pvd, 156 + 10)[0]
        for part in path.strip("\\").split("\\"):
            data = self.read(lba, size)
            i = 0
            found = False
            while i < len(data):
                n = data[i]
                if n == 0:
                    i = (i // 2048 + 1) * 2048
                    continue
                name = data[i + 33:i + 33 + data[i + 32]].decode("latin-1").split(";")[0]
                if name.upper() == part.upper():
                    lba, size = struct.unpack_from("<I", data, i + 2)[0], struct.unpack_from("<I", data, i + 10)[0]
                    found = True
                    break
                i += n
            if not found:
                raise SystemExit(f"No se encuentra {path} en el disco")
        return lba, size


def vol_entries(vol):
    start = vol.find(b"IX\x00\x02")
    out = []
    for m in re.finditer(rb"IX\x00[\x01\x02]", vol[start:]):
        p = start + m.start()
        off, size = struct.unpack_from(">II", vol, p + 4)
        name = vol[p + 16:p + 40].split(b"\0")[0].decode("latin-1")
        out.append((vol[p + 3], off, size, name))
    return out


def cad_lines(b):
    """Frases de un CAD: registros «08 00 <desplazamiento>» que apuntan a una cadena."""
    out = []
    for i in range(0, len(b) - 12, 2):
        if b[i] == 8 and b[i + 1] == 0:
            off = struct.unpack_from("<H", b, i + 2)[0]
            if 0 < off < len(b) and b[off - 1] in (0, 0xFF):
                s = b[off:b.index(b"\0", off)]
                if s and all(32 <= c < 256 and c != 0xFF for c in s):
                    out.append(s.decode("latin-1"))
    return out


def disc_lines(path):
    disc = Disc(path)
    lba, size = disc.find("TENCHU\\DATA.VOL")
    vol = disc.read(lba, size)
    lines = []
    for typ, off, size, name in vol_entries(vol):
        if typ == 1 and name.startswith("@3_") and name.endswith(".CAD"):  # ANIM\ (inglés)
            for s in cad_lines(vol[off:off + size]):
                if s.strip() and s.strip() not in lines:
                    lines.append(s.strip())
    return lines


def junk(s):
    # Restos en Shift-JIS que el juego nunca muestra.
    return re.search(r"[\x80-\xbf]", s) is not None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lang", nargs="?")
    ap.add_argument("--disc")
    ap.add_argument("--dump")
    a = ap.parse_args()
    if a.dump:
        for s in disc_lines(a.dump):
            print(s)
        return
    src = os.path.join(HERE, "i18n", f"{a.lang}_escenas.tsv")
    table = {}
    long_lines = []
    for n, line in enumerate(open(src, encoding="utf-8"), 1):
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        en, tr = line.split("\t")
        if key(en) in table and table[key(en)] != tr.strip():
            print(f"{src}:{n}: frase repetida con otra traducción: {en!r}", file=sys.stderr)
        table[key(en)] = tr.strip()
        if len(tr.strip()) > MAX_LEN:
            long_lines.append(tr.strip())
    for s in long_lines:
        print(f"aviso: más de {MAX_LEN} caracteres ({len(s)}): {s}", file=sys.stderr)
    if a.disc:
        missing = [s for s in disc_lines(a.disc) if key(s) not in table and not junk(s)]
        for s in missing:
            print(f"falta: {s}", file=sys.stderr)
        print(f"{len(missing)} frases sin traducir", file=sys.stderr)
    out_dir = os.path.join(ROOT, "assets", "lang")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{a.lang}.txt"), "w", encoding="utf-8") as f:
        f.write(f"# Subtítulos de las escenas ({a.lang}). Generado por tools/make_translation.py.\n")
        f.write("# Cada línea: hash FNV-1a de la frase inglesa original <TAB> traducción.\n")
        for k, v in table.items():
            f.write(f"{k:08x}\t{v}\n")
    print(f"{len(table)} frases → assets/lang/{a.lang}.txt")


if __name__ == "__main__":
    main()
