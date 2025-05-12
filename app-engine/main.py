from src import _create_app
from src.common.cloud_logging import CloudLoggingHandler
from dotenv import load_dotenv
import firebase_admin
import os


load_dotenv(".env.local")

def create_app():
    firebase_admin.initialize_app()

    if "GAE_SERVICE" in os.environ:
        CloudLoggingHandler.setup_logging()
    return _create_app()


# variable used by Gunicorn
app = create_app()


if __name__ == "__main__":
    load_dotenv(".env.local")
    # Used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host="localhost", port=8080, debug=True)
