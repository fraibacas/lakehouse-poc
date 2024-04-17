import json
import logging
import os
import random
import requests
import string
import time

from typing import Dict, Optional, List, Tuple


logger = logging.getLogger(__name__)


class SupersetConfigurator:
    """
    Client to initialize superset
    """

    def __init__(self, base_url):
        self.base_url = base_url
        self._token = None
        self._is_ready = False
        self._session = None
        self._login_data = dict(
            password="admin",
            username="admin",
            provider="db",
        )
        self._login_url = f"{base_url}/api/v1/security/login"
        self.catalog_name = os.getenv("CATALOG_NAME", "lakehouse-poc")
        self._wait_until_ready()

    @property
    def session(self):
        if self._session is None:
            self._session = requests.session()
        return self._session

    def _wait_until_ready(self, timeout_seconds: int = 120, sleep_seconds: int = 5):
        start = time.time()
        deadline = start + timeout_seconds
        while True:
            if time.time() > deadline:
                logger.error(
                    f"gave up waiting for superset to be ready after {timeout_seconds} seconds"
                )
                raise RuntimeError("superset is not available")
            try:
                resp = self.session.post(self._login_url, json=self._login_data)
                resp.raise_for_status()
                break
            except Exception as e:
                logger.info("waiting for superset to be ready...")
            time.sleep(sleep_seconds)

    @property
    def token(self):
        if self._token is None:
            resp = self.session.post(self._login_url, json=self._login_data)
            resp.raise_for_status()
            self._token = resp.json()["access_token"]
        return self._token

    @property
    def _auth_header(self):
        return {"Authorization": f"Bearer {self.token}"}

    # --------------------------------
    #       Superset Databases
    # --------------------------------

    def create_trino_db(self):
        db_payload = {
            "database_name": "Trino",
            "engine": "trino",
            "configuration_method": "sqlalchemy_form",
            "engine_information": {
                "disable_ssh_tunneling": False,
                "supports_file_upload": True,
            },
            # "sqlalchemy_uri_placeholder": "engine+driver://user:password@host:port/dbname[?key=value&key=value...]",
            # "extra": '{"allows_virtual_table_explore":true}',
            "expose_in_sqllab": True,
            "sqlalchemy_uri": f"trino://bla@trino:8080/{self.catalog_name}",
        }
        resp = self.session.post(
            f"{self.base_url}/api/v1/database",
            json=db_payload,
            headers=self._auth_header,
        )
        resp.raise_for_status()

    # --------------------------------
    #       Superset Datasets
    # --------------------------------

    def get_dataset_info(self, dataset_id: int) -> Tuple[List[str], str]:
        url = f"{self.base_url}/api/v1/dataset/{dataset_id}"
        resp = self.session.get(url, headers=self._auth_header)
        resp.raise_for_status()
        resp_json = resp.json()
        column_names = []
        date_column = None
        for column_info in resp_json["result"]["columns"]:
            column_names.append(column_info["column_name"])
            if date_column is None and column_info["type"]=="DATE":
                date_column = column_info["column_name"]
        return column_names, date_column

    def create_dataset(self, schema_name: str, table_name: str, db_name: str = "Trino"):
        # get Trino's db id
        get_dbs_url = f"{self.base_url}/api/v1/database"
        resp = self.session.get(get_dbs_url, headers=self._auth_header)
        resp.raise_for_status()
        trino_db_id = [
            x for x in resp.json()["result"] if x["database_name"] == db_name
        ][0]["id"]
        # create dataset
        ds_payload = dict(
            database=trino_db_id,
            schema=schema_name,
            table_name=table_name,
        )
        add_ds_url = f"{self.base_url}/api/v1/dataset"
        resp = self.session.post(add_ds_url, json=ds_payload, headers=self._auth_header)
        resp.raise_for_status()
        resp_json = resp.json()
        resp_json["result"]["id"] = resp_json["id"]
        return resp_json["result"]

    def get_dataset(self, schema_name: str, table_name: str) -> Optional[Dict]:
        url = f"{self.base_url}/api/v1/dataset"
        data = dict(
            filters=[
                dict(
                    col="table_name",
                    opr="eq",
                    value=table_name,
                ),
                dict(
                    col="schema",
                    opr="eq",
                    value=schema_name,
                ),
            ]
        )
        resp = self.session.get(
            url, params={"q": json.dumps(data)}, headers=self._auth_header
        )
        resp.raise_for_status()
        resp_json = resp.json()
        if resp_json["count"] > 0:
            return resp_json["result"][0]
        else:
            return None

    # --------------------------------
    #       Superset Charts
    # --------------------------------

    def get_table_chart(
        self,
        name: str,
    ) -> Optional[Dict]:
        url = f"{self.base_url}/api/v1/chart"
        data = dict(
            filters=[
                dict(
                    col="slice_name",
                    opr="eq",
                    value=name,
                ),
            ]
        )
        resp = self.session.get(
            url, params={"q": json.dumps(data)}, headers=self._auth_header
        )
        resp.raise_for_status()
        resp_json = resp.json()
        if resp_json["count"] > 0:
            return resp_json["result"][0]
        else:
            return None

    def create_table_chart(
        self,
        name: str,
        dataset_id: int,
    ) -> Dict:
        columns, temporal_column = self.get_dataset_info(dataset_id)
        params = dict(
            all_columns=columns,
            query_mode="raw",
        )
        if temporal_column:
            params["temporal_columns_lookup"] = {temporal_column: True}
        payload = dict(
            datasource_id=dataset_id,
            datasource_type="table",
            viz_type="table",
            slice_name=name,
            params=json.dumps(params),
        )
        url = f"{self.base_url}/api/v1/chart"
        resp = self.session.post(url, json=payload, headers=self._auth_header)
        resp.raise_for_status()
        resp_json = resp.json()
        resp_json["result"]["id"] = resp_json["id"]
        return resp_json["result"]

    # --------------------------------
    #       Superset Dashboards
    # --------------------------------

    def get_dashboard(self, name: str):
        url = f"{self.base_url}/api/v1/dashboard"
        data = dict(
            filters=[
                dict(
                    col="dashboard_title",
                    opr="title_or_slug",
                    value=name,
                )
            ]
        )
        resp = self.session.get(
            url, params={"q": json.dumps(data)}, headers=self._auth_header
        )
        resp.raise_for_status()
        resp_json = resp.json()
        if resp_json["count"] > 0:
            return resp_json["result"][0]
        else:
            return None

    def get_dashboard_by_id(self, dashboard_id: int) -> Dict:
        url = f"{self.base_url}/api/v1/dashboard/{dashboard_id}"
        resp = self.session.get(url, headers=self._auth_header)
        resp.raise_for_status()
        return resp.json()["result"]

    def create_dashboard(self, name: str):
        url = f"{self.base_url}/api/v1/dashboard"
        json_metadata = """{"chart_configuration":{},"global_chart_configuration":{"scope":{"rootPath":["ROOT_ID"],"excluded":[]},"chartsInScope":[]},"color_scheme":"","positions":{"DASHBOARD_VERSION_KEY":"v2","ROOT_ID":{"type":"ROOT","id":"ROOT_ID","children":["GRID_ID"]},"GRID_ID":{"type":"GRID","id":"GRID_ID","children":[],"parents":["ROOT_ID"]},"HEADER_ID":{"id":"HEADER_ID","type":"HEADER","meta":{"text":"dedede"}}},"refresh_frequency":0,"shared_label_colors":{},"color_scheme_domain":[],"expanded_slices":{},"label_colors":{},"timed_refresh_immune_slices":[],"cross_filters_enabled":true,"default_filters":"{}","filter_scopes":{}}"""
        payload = dict(dashboard_title=name, json_metadata=json_metadata)
        resp = self.session.post(url, json=payload, headers=self._auth_header)
        resp.raise_for_status()
        resp_json = resp.json()
        resp_json["result"]["id"] = resp_json["id"]
        return resp_json["result"]

    def add_table_chart_to_dashboard(self, dashboard: Dict, chart: Dict):
        def _suffix(length: int = 10) -> str:
            return "".join(
                random.SystemRandom().choice(string.ascii_uppercase + string.digits)
                for _ in range(length)
            )

        url = f"{self.base_url}/api/v1/dashboard/{dashboard['id']}"
        chart_id = chart["id"]
        chart_name = chart["slice_name"]
        json_md = json.loads(dashboard["json_metadata"])
        position_md = json_md["positions"]
        ROW = {
            "children": [],
            "id": f"ROW-{_suffix()}",
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
            "parents": ["ROOT_ID", "GRID_ID"],
            "type": "ROW",
        }
        position_md["GRID_ID"]["children"].append(ROW["id"])
        position_md[ROW["id"]] = ROW
        CHART = {
            "children": [],
            "id": f"CHART-{_suffix()}",
            "meta": {
                "chartId": chart_id,
                "height": 100,
                "sliceName": chart_name,
                "width": 12,
            },
            "parents": ["ROOT_ID", "GRID_ID", ROW["id"]],
            "type": "CHART",
        }
        ROW["children"].append(CHART["id"])
        position_md[CHART["id"]] = CHART
        json_md["positions"] = position_md
        json_md["chart_configuration"] = {'1': {'id': chart_id, 'crossFilters': {'scope': 'global', 'chartsInScope': []}}}
        json_md["global_chart_configuration"]["scope"]["chartsInScope"] = [chart_id]
        resp = self.session.put(
            url, json=dict(json_metadata=json.dumps(json_md)), headers=self._auth_header
        )
        resp.raise_for_status()


if __name__ == "__main__":
    superset_url = "http://superset:8088"
    configurator = SupersetConfigurator(superset_url)
