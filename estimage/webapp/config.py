import os
import datetime


class Config:
    SECRET_KEY = "hulava"
    # LOGIN_PROVIDER_NAME = "google"
    LOGIN_PROVIDER_NAME = "autologin"

    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    GOOGLE_DISCOVERY_URL = (
        "https://accounts.google.com/.well-known/openid-configuration"
    )

    PERIOD = dict(
        start=datetime.datetime(2022, 10, 1),
        end=datetime.datetime(2022, 12, 16),
    )
