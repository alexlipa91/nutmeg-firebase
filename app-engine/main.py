import firebase_admin
from firebase_admin import firestore

from src import _create_app

from dotenv import load_dotenv

load_dotenv(".env.local")
    

def create_app():
    firebase_admin.initialize_app()
    return _create_app(firestore.client())


app = create_app()


if __name__ == "__main__":
    # Used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    app.run(host="localhost", port=8080, debug=True)




