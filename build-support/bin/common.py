""" common build support utils"""
from os import listdir
from os.path import isdir, join
from typing import List

SOURCE_PATH = "src/mitol/"


def list_apps() -> List[str]:
    """List the apps in the repo"""
    return [d for d in listdir(SOURCE_PATH) if isdir(join(SOURCE_PATH, d))]
