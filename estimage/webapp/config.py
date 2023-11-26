import os
import datetime

from ..simpledata import AppData


def _parse_csv(csv):
    if csv == "":
        return []
    else:
        return csv.split(",")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    DATA_DIR = os.environ.get("DATA_DIR", "data")
    LOGIN_PROVIDER_NAME = os.environ.get("LOGIN_PROVIDER_NAME", "autologin")

    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    GOOGLE_DISCOVERY_URL = (
        "https://accounts.google.com/.well-known/openid-configuration"
    )
    PLUGINS = _parse_csv(os.environ.get("PLUGINS", ""))



def read_or_create_config(cls):
    config = cls.load()
    config.save()
    return config
