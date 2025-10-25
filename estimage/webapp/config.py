import os
import datetime

from ..simpledata import AppData


def parse_csv(csv):
    if csv == "":
        return []
    else:
        return csv.split(",")


class CacheConfig:
    CACHE_TYPE = os.environ.get("CACHE_TYPE", "NullCache")


for key, val in os.environ.items():
    if key.startswith("CACHE_"):
        setattr(CacheConfig, key, val)


class CommonConfig(CacheConfig):
    SECRET_KEY = os.environ.get("SECRET_KEY")
    LOGIN_PROVIDER_NAME = os.environ.get("LOGIN_PROVIDER_NAME", "autologin")

    GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", None)
    GOOGLE_DISCOVERY_URL = (
        "https://accounts.google.com/.well-known/openid-configuration"
    )


class Config(CommonConfig):
    DATA_DIR = os.environ.get("DATA_DIR", "data")
    PLUGINS = parse_csv(os.environ.get("PLUGINS", ""))
    BACKEND = os.environ.get("BACKEND", "toml")


class MultiheadConfig(CommonConfig):
    DATA_DIRS = parse_csv(os.environ.get("DATA_DIRS", "data"))


def read_or_create_config(cls):
    config = cls.load()
    config.save()
    return config
