import unittest

from chimera_one.knowledge import query


class KnowledgeTests(unittest.TestCase):
    def test_query_preserves_provenance(self):
        index = {"records": [{"repository":"R","role":"verify","path":"docs/a.md","kind":"documentation","bytes":10,"sha256":"abc","text":"proof carrying evidence runtime"}]}
        result = query(index, "evidence")
        self.assertEqual(result[0]["repository"], "R")
        self.assertEqual(result[0]["sha256"], "abc")
        self.assertIn("evidence", result[0]["snippet"])


if __name__ == "__main__":
    unittest.main()
