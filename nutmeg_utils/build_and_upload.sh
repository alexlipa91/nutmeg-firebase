rm -rf dist/
python3 -m setup.py bdist_wheel
python3 -m twine upload --repository-url https://us-central1-python.pkg.dev/nutmeg-9099c/quickstart-python-repo/ dist/*
