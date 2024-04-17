import duckdb
import os

from pathlib import Path
from typing import Optional

from prefect import flow, get_run_logger
from pydantic import BaseModel

from iceberg import IcebergClient
from superset import SupersetConfigurator


DATA_FOLDER = os.getenv("LAKEHOUSE_DATA_PATH", "/lakehouse-poc")


class IngestionRequest(BaseModel):
    url: str
    db_name: str
    table_name: str
    has_header: Optional[bool] = True
    date_format: Optional[str] = None
    timestamp_format: Optional[str] = None
    normalize_column_names: Optional[bool] = True


default_ingestion_request = IngestionRequest(
    url=f"{DATA_FOLDER}/datasets/yellow_tripdata_2024-01.parquet",
    db_name="nyc-taxi",
    table_name="yellow_tripdata",
)


@flow
def data_to_dashboard(
    request: IngestionRequest = default_ingestion_request,
    superset_url: str = "http://superset:8088",
):
    logger = get_run_logger()
    logger.info(f"ingesting {request.url}")

    file_extension = Path(request.url).suffix
    if file_extension not in [".csv", ".parquet"]:
        raise ValueError(f"unsupported file format {request.url}")
    # --
    # load data with duckdb
    # --
    if file_extension == ".csv":
        read_csv_kwargs = dict(
            header=request.has_header, normalize_names=request.normalize_column_names
        )
        if request.date_format:
            read_csv_kwargs["date_format"] = request.date_format
        if request.timestamp_format:
            read_csv_kwargs["timestamp_format"] = request.timestamp_format
        duckdb_data = duckdb.read_csv(request.url, **read_csv_kwargs)
    else:
        duckdb_data = duckdb.read_parquet(request.url)
    arrow_table_data = duckdb_data.to_arrow_table()
    # --
    # create iceberg db, table and add data
    # --
    iceberg = IcebergClient()
    iceberg.create_namespace(
        request.db_name,
        properties=dict(customer_name=request.db_name, owner="bla@lakehouse.com"),
        recreate_if_exists=True,
    )
    table = iceberg.create_table(
        namespace=request.db_name,
        table=request.table_name,
        schema=arrow_table_data.schema,
    )
    table.append(arrow_table_data)
    # --
    # Configure Superset
    # --
    dashboard_name = f"LAKEHOUSE_POC.{request.db_name}.{request.table_name}"
    chart_name = f"{request.db_name}.{request.table_name}"

    configurator = SupersetConfigurator(superset_url)
    logger.info("configuring superset...")
    dataset = configurator.get_dataset(
        schema_name=request.db_name, table_name=request.table_name
    )
    if dataset is None:
        dataset = configurator.create_dataset(
            schema_name=request.db_name, table_name=request.table_name
        )
        logger.info("superset dataset created!")
    dashboard = configurator.get_dashboard(dashboard_name)
    if dashboard is None:
        dashboard = configurator.create_dashboard(dashboard_name)
        logger.info("superset dashboard created!")
    chart = configurator.get_table_chart(chart_name)
    if chart is None:
        # create chart
        chart = configurator.create_table_chart(
            name=chart_name,
            dataset_id=dataset["id"],
        )
        logger.info("superset chart created!")
        # add chart to dashboard
        configurator.add_table_chart_to_dashboard(dashboard, chart)


if __name__ == "__main__":
    data_to_dashboard(default_ingestion_request)
