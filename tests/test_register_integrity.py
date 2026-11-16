import unittest

from tools.check_register_append import verify


class RegisterIntegrityTest(unittest.TestCase):
    base = b"# Register\n## Rules\nOwner approval required\n## Evidence\nOld receipt\n"

    def test_append(self):
        verify(self.base, self.base + b"New receipt\n")

    def test_unchanged(self):
        verify(self.base, self.base)

    def test_invalid_candidates(self):
        for candidate in (
            self.base[:-4],
            self.base[:20] + b"\x00\xff",
            self.base.replace(b"## Rules\n", b""),
            self.base + b"\x00",
            self.base + b"\xff",
        ):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                verify(self.base, candidate)

    def test_empty_base_and_line_boundaries(self):
        for base, proposed in ((b"", b"receipt"), (b"old", b"oldjoined"), (b"old\n", b"old\r\n")):
            with self.subTest(base=base, proposed=proposed), self.assertRaises(ValueError):
                verify(base, proposed)
        verify(b"old", b"old\nnew\n")
