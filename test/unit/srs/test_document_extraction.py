"""Reading the formats requirements actually arrive in.

Everything that was not a PDF, a picture or a recording used to be decoded as
if it were plain text. A Word file is a zip, so a specification someone spent
an afternoon writing reached the model as a page of zip bytes - and the model
read it anyway, because nothing told it not to.
"""
from __future__ import annotations

import io
import unittest
import zipfile

from test import _support  # noqa: F401
from srs_agent.app.extraction import read_archive, read_document, read_text


def zipped(files: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return buffer.getvalue()


class DocumentTests(unittest.TestCase):
    def docx(self, *paragraphs):
        body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
        return zipped({"word/document.xml": f"<w:document><w:body>{body}</w:body></w:document>"})

    def test_a_word_file_reads_as_its_words(self):
        got = read_document(self.docx("Soup counter", "A member books a bench."), "spec.docx")
        self.assertEqual(got["text"], "Soup counter\nA member books a bench.")

    def test_escaped_characters_come_back_as_themselves(self):
        got = read_document(self.docx("Books &amp; benches &lt;3"), "spec.docx")
        self.assertEqual(got["text"], "Books & benches <3")

    def test_slides_are_read_in_the_order_they_are_shown(self):
        slide = lambda text: f"<p:sld><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:sld>"
        deck = zipped({f"ppt/slides/slide{n}.xml": slide(f"Slide {n}") for n in (1, 2, 10)})
        got = read_document(deck, "deck.pptx")
        self.assertEqual([line for line in got["text"].splitlines() if line.strip()],
                         ["Slide 1", "Slide 2", "Slide 10"])

    def test_a_spreadsheet_gives_up_its_labels(self):
        book = zipped({"xl/sharedStrings.xml":
                       "<sst><si><t>Dish</t></si><si><t>Price</t></si></sst>"})
        self.assertIn("Dish", read_document(book, "menu.xlsx")["text"])

    def test_the_old_binary_word_format_says_what_to_do_instead(self):
        got = read_document(b"\xd0\xcf\x11\xe0rubbish", "spec.doc")
        self.assertEqual(got["text"], "")
        self.assertIn(".docx", got["warning"])

    def test_a_file_that_is_not_really_a_document_is_an_error_not_a_crash(self):
        got = read_document(b"not a zip at all", "spec.docx")
        self.assertEqual(got["text"], "")
        self.assertIn("could not be opened", got["error"])


class ArchiveTests(unittest.TestCase):
    def bundle(self):
        return zipped({
            "brand/colors.md": "# Brand\nPrimary: #EA580C",
            "data/menu.csv": "name,price\nSoup,4.50",
            "logo.png": b"\x89PNG\r\n\x1a\n" + b"0" * 40,
        })

    def test_every_entry_is_named(self):
        text = read_archive(self.bundle(), "assets.zip")["text"]
        for name in ("brand/colors.md", "data/menu.csv", "logo.png"):
            self.assertIn(name, text)

    def test_the_text_inside_is_quoted(self):
        text = read_archive(self.bundle(), "assets.zip")["text"]
        self.assertIn("Primary: #EA580C", text)
        self.assertIn("Soup,4.50", text)

    def test_a_picture_is_only_promised_when_something_kept_it(self):
        without = read_archive(self.bundle(), "assets.zip")
        self.assertNotIn("/generated/", without["text"])

        kept = []
        with_saving = read_archive(self.bundle(), "assets.zip",
                                   save_image=lambda name, blob: (kept.append(name),
                                                                  "/generated/logo.png")[1])
        self.assertEqual(kept, ["logo.png"])
        self.assertIn("/generated/logo.png", with_saving["text"])
        self.assertEqual(with_saving["images"], 1)

    def test_a_broken_archive_is_an_error_not_a_crash(self):
        got = read_archive(b"PK not really", "broken.zip")
        self.assertEqual(got["text"], "")
        self.assertIn("could not be opened", got["error"])


class PlainTextTests(unittest.TestCase):
    def test_text_is_read_as_text(self):
        self.assertEqual(read_text("a café menu".encode("utf-8"), "menu.txt")["text"],
                         "a café menu")

    def test_a_binary_says_so_instead_of_arriving_as_noise(self):
        got = read_text(b"\x00\x01\x02\x03rubbish", "thing.bin")
        self.assertEqual(got["text"], "")
        self.assertIn("not a text file", got["warning"])

    def test_almost_utf8_is_kept_and_the_loss_is_admitted(self):
        got = read_text("price: 4.50\n".encode("utf-8") + b"\xff\xfe", "prices.csv")
        self.assertIn("price: 4.50", got["text"])
        self.assertIn("unreadable bytes", got["warning"])


if __name__ == "__main__":
    unittest.main()
