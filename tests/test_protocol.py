from __future__ import annotations

import json
import unittest
from pathlib import Path

from chimera_one.protocol import canonical_json, protocol_digest, validate_run

ROOT = Path(__file__).resolve().parents[1]


class ProtocolTests(unittest.TestCase):
    def test_canonical_digest_is_key_order_independent(self) -> None:
        self.assertEqual(protocol_digest({"z": 2, "a": 1}), protocol_digest({"a": 1, "z": 2}))

    def test_float_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            canonical_json({"not_allowed": 0.5})

    def test_reference_run_is_valid(self) -> None:
        run = json.loads((ROOT / "tests/vectors/run.valid.json").read_text())
        report = validate_run(run)
        self.assertTrue(report["valid"], report["errors"])

    def test_mutation_policy_fails_closed(self) -> None:
        run = json.loads((ROOT / "tests/vectors/run.valid.json").read_text())
        run["policy"]["automatic_mutation"] = True
        report = validate_run(run)
        self.assertFalse(report["valid"])


if __name__ == "__main__":
    unittest.main()
