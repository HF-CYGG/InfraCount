import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DeploymentConfigContractTests(unittest.TestCase):
    def test_all_application_environment_variables_are_exposed_by_compose_and_example(self):
        config_source = (ROOT / "app" / "config.py").read_text(encoding="utf-8")
        config_names = set(
            re.findall(
                r'(?:os\.getenv|_env_bool|_env_csv)\("([A-Z0-9_]+)"',
                config_source,
            )
        )

        compose_source = (ROOT / "docker" / "docker-compose.yml").read_text(
            encoding="utf-8"
        )
        compose_names = set(
            re.findall(r"^      ([A-Z0-9_]+):", compose_source, flags=re.MULTILINE)
        )

        env_source = (ROOT / ".env.example").read_text(encoding="utf-8")
        example_names = set(
            re.findall(r"^([A-Z0-9_]+)=", env_source, flags=re.MULTILINE)
        )

        self.assertEqual(config_names - compose_names, set())
        self.assertEqual(config_names - example_names, set())


if __name__ == "__main__":
    unittest.main()
