from price_touch.api import create_app
from price_touch.config import Settings
from price_touch.storage import SnapshotStore

settings = Settings()
store = SnapshotStore()
app = create_app(store=store, settings=settings)
