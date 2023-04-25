import os

import jinja2

templateLoader = jinja2.FileSystemLoader(searchpath="./scripts")
templateEnv = jinja2.Environment(loader=templateLoader)
TEMPLATE_FILE = "app.yaml.j2"
template = templateEnv.get_template(TEMPLATE_FILE)

outputText = template.render(env=os.environ)

with open("app.yaml", "w") as fh:
    fh.write(outputText)
