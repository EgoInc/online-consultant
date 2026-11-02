"""Student thesis entry point. Catalog algorithms deliberately remain empty."""


class CatalogEngine:
    def connect(self, name: str, source: dict) -> dict:
        """Import API/file source, normalize all products and persist in our DB.

        source.type is api (catalog_url, product_url_template) or file (UploadedFile).
        Preserve original IDs and attributes alongside normalized data.
        Return {store_id, status: pending} when catalog preparation is scheduled.
        """
        raise NotImplementedError

    def status(self, store_id: str) -> dict:
        """Return public preparation metrics scoped to this store."""
        raise NotImplementedError

    def search(self, store_id: str, query: str, constraints: list, limit: int) -> list:
        """Return normalized Product DTOs. Never query another store's data."""
        raise NotImplementedError
