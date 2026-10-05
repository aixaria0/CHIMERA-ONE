import json
import tempfile
import unittest
from pathlib import Path

from chimera_one.catalog import Capability
from chimera_one.federation import FederationError, federation_report, validate_provider


def provider(entry):
    return {
        "schema": "chimera-provider/v1",
        "repository": "a/X",
        "role": "verify",
        "control_plane": "aixaria0/CHIMERA-ONE",
        "version": "1",
        "entrypoints": [entry],
        "boundaries": ["bounded"],
    }


class FederationTests(unittest.TestCase):
    def test_provider_manifest_must_agree_with_registry(self):
        cap = Capability({"id": "x.cap", "provider": "X"})
        constellation = {
            "repositories": [
                {"name": "X", "role": "verify", "url": "https://github.com/a/X", "checkout": "X"}
            ]
        }
        manifest = provider(
            {
                "capability": "x.cap",
                "command": ["x"],
                "mode": "verification",
                "network": "none",
                "mutation": "none",
            }
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "X"
            root.mkdir()
            (root / "chimera.provider.json").write_text(json.dumps(manifest))
            report = federation_report(Path(tmp), constellation, [cap])
        self.assertTrue(report["valid"])

    def test_bounded_service_entrypoint_is_valid(self):
        validate_provider(
            provider(
                {
                    "capability": "x.cap",
                    "mode": "bounded-execution",
                    "network": "loopback",
                    "mutation": "none",
                    "transport": "http",
                    "endpoint": {"method": "POST", "path": "/execute", "protocol": "x/v1"},
                }
            )
        )

    def test_entrypoint_requires_exactly_one_invocation_form(self):
        with self.assertRaises(FederationError):
            validate_provider(
                provider(
                    {
                        "capability": "x.cap",
                        "mode": "verification",
                        "network": "none",
                        "mutation": "none",
                    }
                )
            )


if __name__ == "__main__":
    unittest.main()
