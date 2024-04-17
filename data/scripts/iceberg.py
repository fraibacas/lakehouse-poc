import logging

from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.table import Table


from typing import Set, Dict, Optional


logger = logging.getLogger(__name__)


class IcebergClient:

    def __init__(self, location: Optional[str] = "s3a://warehouse/"):
        self._catalog = None
        self.location = location

    @property
    def catalog(self):
        if self._catalog is None:
            self._catalog = load_catalog()
        return self._catalog

    @property
    def namespaces(self) -> Set:
        return {x[0] for x in self.catalog.list_namespaces()}

    def namespace_properties(self, namespace: str) -> Dict:
        return dict(
            name=namespace, propeties=self.catalog.load_namespace_properties(namespace)
        )

    def delete_namespace(self, namespace: str):
        for table in self.catalog.list_tables(namespace=namespace):
            self.catalog.drop_table(table)
        self.catalog.drop_namespace(namespace=namespace)

    def create_namespace(
        self,
        namespace: str,
        properties: Optional[Dict] = None,
        recreate_if_exists: bool = False,
    ):
        if namespace in self.namespaces:
            logger.info("namespace {namespace} exists")
            if recreate_if_exists:
                logger.info(f"recreating namespace {namespace}...")
                self.delete_namespace(namespace)
        self.catalog.create_namespace(
            namespace=namespace,
            properties=properties,
        )
        logger.info(f"namespace created <{namespace}>")

    def create_table(self, namespace: str, table: str, schema: Schema):
        return self.catalog.create_table(
            identifier=f"{namespace}.{table}",
            location=f"{self.location}/{namespace}",
            schema=schema,
        )
