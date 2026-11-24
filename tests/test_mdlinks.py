import unittest

from mdlinks import iter_links


class MarkdownLinksTest(unittest.TestCase):
    def test_images_titles_and_line_numbers(self):
        source = '[![地图](map.png)](docs/index.md)\n\n[图](<图 片/a.png> "预览")'
        self.assertEqual(list(iter_links(source)), [
            (1, "map.png"), (1, "docs/index.md"), (3, "图 片/a.png")
        ])

    def test_balanced_parentheses_and_escapes(self):
        source = r"[note](a(b(c)).md 'title') [two](c\(1\).md) [book](a&amp;b.md)"
        self.assertEqual(list(iter_links(source)), [
            (1, "a(b(c)).md"), (1, "c(1).md"), (1, "a&b.md")
        ])

    def test_code_and_escaped_openers(self):
        source = (
            r"\[literal](no) `[code](no)` ``hello ` [example](no)`` [real](yes)"
            "\n\n    [indented](no)\n~~~~py\n[hidden](no)\n~~~\n"
            "[still hidden](no)\n~~~~\n[visible](also-yes)"
        )
        self.assertEqual(list(iter_links(source)), [(1, "yes"), (9, "also-yes")])

    def test_reference_definition_checked_once(self):
        source = "[see][a] [a][]\n[a]: <docs/A B.md> (read this)\n[unused]: gone.md"
        self.assertEqual(list(iter_links(source)), [(2, "docs/A B.md"), (3, "gone.md")])

    def test_malformed_links(self):
        source = "[a](<dangling)\n[b](file trailing)\nloose](ignored)\n[c](a(b)"
        self.assertEqual(list(iter_links(source)), [])

    def test_code_literal_and_empty_destination(self):
        source = "`unclosed [read](ok)\n[home]()"
        self.assertEqual(list(iter_links(source)), [(1, "ok"), (2, "")])
