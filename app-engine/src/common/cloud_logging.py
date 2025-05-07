import logging
import flask
import google.cloud.logging


class CloudLoggingHandler(logging.Handler):

    @staticmethod
    def setup_logging():
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)

        # Remove any existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Add our custom Cloud Logging handler
        handler = CloudLoggingHandler()
        logger.addHandler(handler)

    def __init__(self):
        super().__init__()
        self.logging_client = google.cloud.logging.Client()
        self.logger = self.logging_client.logger("app")

    def emit(self, record):
        try:  # Create base structured log
            structured_log = {
                "message": record.getMessage(),
                "severity": record.levelname,
            }

            # Only try to access Flask context if we're in an application context
            if flask.has_app_context():
                # Add user_id if available
                if hasattr(flask.g, "uid"):
                    structured_log["user_id"] = flask.g.uid
                structured_log["client_version"] = flask.request.headers.get(
                    "App-Version", "unknown"
                )

            # Log using the Cloud Logging client
            self.logger.log_struct(structured_log, severity=record.levelname)
        except Exception:
            self.handleError(record)
