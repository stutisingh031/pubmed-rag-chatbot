import logging
import logging.handlers
import uuid
from contextvars import ContextVar
from .config import LOG_DIR

request_id_var: ContextVar[str] = ContextVar("request_id", default="startup")

class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True

def configure_logging():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if root.handlers:
        return
    fmt = logging.Formatter("%(asctime)s %(levelname)s request_id=%(request_id)s %(name)s: %(message)s")
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    rotating = logging.handlers.RotatingFileHandler(LOG_DIR / "app.log", maxBytes=1_500_000, backupCount=3, encoding="utf-8")
    rotating.setFormatter(fmt)
    for handler in (stream, rotating):
        handler.addFilter(RequestIdFilter())
        root.addHandler(handler)
    root.setLevel(logging.INFO)

def new_request_id():
    return uuid.uuid4().hex
