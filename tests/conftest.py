import os


def pytest_configure(config):
    os.environ["SOVEREIGN_DEV_TOKEN"] = "dev-token-sovereign-ai-ui"
