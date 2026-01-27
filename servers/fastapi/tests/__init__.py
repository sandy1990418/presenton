import os


_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if os.getcwd() != _BASE_DIR:
    os.chdir(_BASE_DIR)
