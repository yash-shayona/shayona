# shayona/migrate.py
from shayona.setup.navigation import sync_navigation


def after_migrate():
    # your existing work...
    sync_navigation()
