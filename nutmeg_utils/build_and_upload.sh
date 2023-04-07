rm -rf dist/
python3 -m setup.py bdist_wheel
python3 -m twine upload -r quickstart-python-repo dist/* --verbose
