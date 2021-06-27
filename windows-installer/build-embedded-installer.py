#!/usr/bin/env python
# -*- coding: utf-8 -*-
import hashlib
import os
import shutil
import subprocess
import urllib.request
import zipfile

from contextlib import contextmanager
from pathlib import Path

""" This script is based on following articles:
* https://dev.to/fpim/setting-up-python-s-windows-embeddable-distribution-properly-1081
* https://docs.python.org/3.6/using/windows.html#finding-modules
* https://docs.python.org/3.8/using/windows.html#windows-embeddable
"""


@contextmanager
def pushd(new_dir):
    previous_dir = os.getcwd()
    os.chdir(new_dir)
    try:
        yield
    finally:
        os.chdir(previous_dir)


# Variables
app_name = "toggl2tempo"

source_dir = Path("..")

env_dir = source_dir.joinpath("venv", "Scripts")
python_path = str(env_dir.joinpath("python.exe").resolve())
pip_path = str(env_dir.joinpath("pip.exe").resolve())

dist_dir = source_dir.joinpath("dist")
package_dir = dist_dir.joinpath("package")
libs_dir = package_dir.joinpath("libs")

python_embedded_version = "python38"
python_embedded_file_name = "python-3.8.10-embed-amd64.zip"
python_embedded_file_hash_sum = "abbe314e9b41603dde0a823b76f5bbbe17b3de3e5ac4ef06b759da5466711271"
python_embedded_url = "https://www.python.org/ftp/python/3.8.10/python-3.8.10-embed-amd64.zip"
python_embedded_file_path = dist_dir.joinpath(python_embedded_file_name)

# === Read version ===
print("Read version ...")
version_file = source_dir.joinpath("version")
with version_file.open(mode="r", encoding='ascii') as f:
    version = f.read()

# === Remove old package directory
print("Cleanup artifacts of previous build ...")
if package_dir.exists():
    shutil.rmtree(package_dir)

if not dist_dir.exists():
    dist_dir.mkdir()

if not package_dir.exists():
    package_dir.mkdir()

# === Download Python Embedded dist package ===
print("Download Python Embedded dist package ...")
if not python_embedded_file_path.exists():
    urllib.request.urlretrieve(python_embedded_url, python_embedded_file_path)

# Check hash sum
print("Check hash sum ...")
h = hashlib.sha256()

with python_embedded_file_path.open(mode="rb") as f:
    while True:
        block = f.read(2048)
        if len(block) == 0:
            break

        h.update(block)

h.digest()

current_hash_sum = h.hexdigest()
if python_embedded_file_hash_sum != current_hash_sum:
    raise Exception(f"Hash sum {current_hash_sum} of downloaded '{python_embedded_file_name}' \
      doesn't match with expected {python_embedded_file_hash_sum}")

# === Prepare Python embedded dist ===
print("Prepare Python embedded dist ...")

# Unzip archive with Python binaries embedded
with zipfile.ZipFile(python_embedded_file_path, 'r') as zip_ref:
    zip_ref.extractall(package_dir)

# Rename archive with Python bytecode
python_pyc_archive = package_dir.joinpath(f"{python_embedded_version}.zip")
python_pyc_archive = python_pyc_archive.rename(python_pyc_archive.with_name(f"_{python_embedded_version}.zip"))

# Create dir for Python bytecode
python_pyc_dir = package_dir.joinpath(f"{python_embedded_version}.zip")
python_pyc_dir.mkdir()

# Unzip the archive of Python bytecode
with zipfile.ZipFile(python_pyc_archive, 'r') as zip_ref:
    zip_ref.extractall(python_pyc_dir)

# Remove original archive of Python bytecode
python_pyc_archive.unlink()

# Update file of Python paths
path_file = package_dir.joinpath(f"{python_embedded_version}._pth")
with path_file.open(mode="w", encoding="utf-8") as f:
    f.write(f"""
libs
{python_embedded_version}.zip
.

import site
""")

# === Build wheel distribution package ===
print("Build Wheel distribution packages ...")
with pushd(source_dir):
    bdist_process = subprocess.run([python_path, 'setup.py', "sdist", "bdist_wheel", "--embedded"],
                                   stdout=subprocess.PIPE,
                                   universal_newlines=True)
    if bdist_process.returncode != 0:
        exit(bdist_process.returncode)

# === Install application and requirements ===
print("Install application and requirements ...")
wheel_package_path = dist_dir.joinpath(f"toggl2tempo-{version}-py3-none-any.whl")
pip_process = subprocess.run([pip_path, 'install', "-t", libs_dir, wheel_package_path],
                             stdout=subprocess.PIPE,
                             universal_newlines=True)
if pip_process.returncode != 0:
    exit(pip_process.returncode)

# Copy main script
shutil.copy(source_dir.joinpath("main.py"), package_dir.joinpath(f"{app_name}.py"))

# === Run NSIS to build Windows installer ===
print("Make Windows installer ...")
makensis_process = subprocess.run(['makensis.exe', 'embedded-installer.nsi'],
                                  stdout=subprocess.PIPE,
                                  universal_newlines=True)
if makensis_process.returncode != 0:
    exit(makensis_process.returncode)

print("Success!")
