import os
import shutil
import sys


def app_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(__file__))


def bundle_base_dir():
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return app_base_dir()


def app_path(*parts):
    return os.path.join(app_base_dir(), *parts)


def resource_path(*parts):
    return os.path.join(bundle_base_dir(), *parts)


def ensure_app_dir(*parts):
    path = app_path(*parts)
    os.makedirs(path, exist_ok=True)
    return path


def ensure_app_file(*parts, source_parts=None):
    destination = app_path(*parts)
    os.makedirs(os.path.dirname(destination), exist_ok=True)

    if os.path.exists(destination):
        return destination

    source = resource_path(*(source_parts or parts))
    if os.path.isfile(source):
        try:
            shutil.copy2(source, destination)
        except OSError:
            pass

    return destination
