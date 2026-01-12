import struct
import os

class GTOBTable:
    def __init__(self, path: str):
        self.path = path
        self.lut = {}
        self._load()

    def _load(self):
        with open(self.path, "rb") as f:
            magic, version, count, _ = struct.unpack("<4sHIH", f.read(12))
            assert magic == b"GTOB"

            for _ in range(count):
                data = f.read(5)
                if len(data) < 5:
                    break

                hid, qf, qc, qr = struct.unpack("<HBBB", data)
                total = qf + qc + qr
                if total == 0:
                    continue

                self.lut[hid] = {
                    "fold": qf / 255.0,
                    "call": qc / 255.0,
                    "raise": qr / 255.0,
                }

    def get(self, hid, default=None):
        return self.lut.get(hid, default)

    def __contains__(self, hid):
        return hid in self.lut

    def __len__(self):
        return len(self.lut)
