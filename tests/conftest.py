import os
os.environ["F1_AUTO_SYNC"] = "0"

def pytest_addoption(parser):
    parser.addoption("--live-db", action="store_true", help="Require and test the configured MySQL database")
