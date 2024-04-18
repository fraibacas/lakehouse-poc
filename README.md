# Lakehouse 

Docker compose stack to run an open-source lakehouse on a single machine using Prefect, Iceberg, Trino and Superset.

![](/docs/lakehouse.png)


## Prerequisites

In order to run the stack a Linux, Windows or MacOS computer with the following dependencies installed is needed:

* docker
* docker-compose
* bash
* wget

Notes:
* The docker-compose version should support `dockerfile_inline` which was released in version [2.17](https://github.com/docker/compose/releases/tag/v2.17.0)
* Windows deployment has not been tested but it should work with WSL and Docker Desktop
* The following ports should be available: 80, 4200, 5006, 8088


## Getting Started

* Clone this repository and `cd` into it.
* Use the `lakehouse.sh` bash script to start/stop the stack. Options:
    - `lakehouse.sh start`: initialize environment (if needed) and start all services.
    - `lakehouse.sh stop`: stop all services.
    - `lakehouse.sh restart`: restart all services.
    - `lakehouse.sh status`: displays services' status.
    - `lakehouse.sh reset`: reset environment. All ingested data will be deleted.


## Environment Configuration and Initizalization

The environment is configured by default to run on Docker Desktop. When running on Linux, you will need to edit `.env` file and set the value of variable `HOST_OR_IP` to the machine's ip or dns.

Example:
```
# HOST_OR_IP=host.docker.internal
HOST_OR_IP=10.10.10.10
```

No other config changes are needed. `lakehouse.sh start` initializes all services including databases, Prefect deployment registration, etc.

Initizalization will automatically run the first time the environment is started and the first time the enviroment is started after an environment reset.


## Services

The LakeHouse stack contains the following services:

* `traefik`: Reverse proxy.
* `iceberg`: Iceberg metadata catalog.
* `minio`: table storage for Iceberg.
* `trino`: query engine.
* `superset`: data exploration and visualization.
* `jupyter`: notebook configured to access Iceberg and Trino.
* `prefect-server`: workflow engine server used for data ingestion.
* `prefect-worker`: workflow engine worker.
* `postgres`: SQL database used by Prefect, Superset and Iceberg metadata catalog.


Some of the services provide user interfaces. These are their urls:
* Prefect:     http://localhost:4200
* Superset:    http://localhost:8088  (admin/admin)
* Jupyter:     http://localhost:5006

Alteratively, the following urls can be used after updating your `/etc/hosts`.
* Jupyter:     http://jupyter.lakehouse.localhost
* Prefect:     http://prefect.lakehouse.localhost
* Superset:    http://superset.lakehouse.localhost

```
# /etc/hosts
127.0.0.1 jupyter.lakehouse.localhost prefect.lakehouse.localhost superset.lakehouse.localhost trino.lakehouse.localhost minio.lakehouse.localhost
```

## Data Ingestion

When the enviroment is initialized, the Prefect Flow `data-to-dashboard` is automatically registered. This flow ingests `csv` or `parquet` files using DuckDB and creates a simple dashboard for the ingested data. 

### Ingesting sample data with Prefect

A sample dataset is provided and can be ingested following the following steps:

* Navigate to Prefect's UI -> Deployments.
* Click on the three dots to the right of the `data-to-dashboard:dev` deployment.
* Select `Quick run`.

![](/docs/prefect_deployment.png)

* After the flow run is started, you can navigate to the `Flow Runs` section and see the flow's logs.

![](/docs/prefect_flow_run.png)

* Once the flow run has successfully completed, navigate to Superset UI. A dashboard with a sample table chart should be available.

![](/docs/superset.png)

### Ingesting sample data with Jupyter

A sample jupyter notebook is provided with code to ingest and query a parquet file:

* Navigate to Jupiter's UI.
* Open the notebook `notebooks/lakehouse.ipynb.

![](/docs/jupyter.png)

* Run the notebook.
* Once the notebook successfully ran, navigate to Superset UI. A dashboard with a sample table chart should be available.

### Ingesting your own data with Prefect

Custom csv or parquet files can be ingested with Prefect:

* Copy the data file into folder `data/datasets`.
* Navigate to Prefect's UI -> Deployments.
* Click on the three dots to the right of the `data-to-dashboard:dev` deployment.
* Select `Custom run`.
* Set the url for your file. It should start with `/lakehouse-poc/datasets/`.

![](/docs/prefect_custom_run.png)

* Set database name (Iceberg namespace) and table name.
* All other parameters are optional and apply to csv files only.
* Click on `Submit`.
* After the flow run is started, you can navigate to the `Flow Runs` section and see the flow's logs.
* Once the notebook successfully ran, navigate to Superset UI. A dashboard with a sample table chart should be available. A `datetime` column is required for the dashboard to work.

## Future updates

* Add Spark for ingestion and query.
* Add option to use Nessie as Iceberg catalog. Currently waiting for [pyiceberg](https://github.com/apache/iceberg-python/issues/19) to add support for it.

