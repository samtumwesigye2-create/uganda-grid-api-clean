"""WMS400Vector records facade.

The existing Vector 5250 backend remains the production implementation while
WMS400Vector becomes the canonical system identity. Importing this module does
not duplicate or migrate the database.
"""

from vector5250_records import router

SYSTEM_NAME = "WMS400Vector"
LEGACY_DATABASE = "vector5250.db"
ACCESS_CLASSIFICATION = "CORPORATE_ONLY"

__all__ = ["router", "SYSTEM_NAME", "LEGACY_DATABASE", "ACCESS_CLASSIFICATION"]
