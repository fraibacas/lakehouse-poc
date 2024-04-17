#!/bin/bash

set -e
set +x

LOCAL_ENV_FILE=.env
VOLUMES_FOLDER=./volumes
INITIALIZED_MARKER=./volumes/.initialized

DOCKER_COMPOSE=docker-compose

SAMPLE_PARQUET_FILE=f"{DATA_FOLDER}/datasets/yellow_tripdata_2024-01.parquet"

# ------------------------------------

function prepare_environment() {
    if [ -f "${LOCAL_ENV_FILE}" ]; then
        for line in `cat ${LOCAL_ENV_FILE} | grep -v ^#`
        do
            eval "export $line"
        done
    fi
    local catalog="iceberg"
    local catalog_uri="http://iceberg:8181"
    if [ "${ICEBERG_CATALOG}" = "NESSIE" ]; then
        catalog="nessie"
        catalog_uri="http://nessie:19120/api"
    fi
    export ICEBERG_CATALOG_URI=${catalog_uri}
    export ICEBERG_CATALOG_SVC=${catalog}
}

function wait_until_postgres_ready() {
    local iterations=0
    local max_iterations=40
    while [ ${iterations} -le ${max_iterations} ]; do
        set +e
        ${DOCKER_COMPOSE} exec postgres bash -c 'pg_isready | grep "accepting connections"' > /dev/null 2>&1
        local ready=$?
        set -e
        if [ ${ready} -eq 0 ]; then
            break
        else
            echo "waiting for postgres to be ready"
            sleep 5
        fi
        (( iterations = iterations + 1 ))
    done
    if [ "${iterations}" -gt ${max_iterations} ]; then
        echo "error starting postgres"
        exit 1
    fi
}

function download_sample_dataset() {
    local filepath=${PWD}/data/datasets/yellow_tripdata_2024-01.parquet
    if [ ! -f ${filepath} ]; then
        echo "downloading sample data..."
        wget https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2024-01.parquet -O ${filepath}
    fi
}

function start_databases() {
    ${DOCKER_COMPOSE} up -d --force-recreate --no-deps --remove-orphans postgres minio
    wait_until_postgres_ready
    sleep 1
}

function init_environment() {
    # -----
    # minio initialization
    # -----
    ${DOCKER_COMPOSE} exec minio /bin/bash -c "
      until (mc config host add minio http://minio:9000 ${MINIO_ROOT_USER} ${MINIO_ROOT_PASSWORD}) do echo '...waiting...' && sleep 1; done;
      mc mb minio/${WAREHOUSE_BUCKET_NAME};
      mc policy set public minio/${WAREHOUSE_BUCKET_NAME};
    "
    # -----
    # superset database initialization
    # -----
    ${DOCKER_COMPOSE} exec postgres /bin/bash -c "
PGPASSWORD=${POSTGRES_PASSWORD} psql --host postgres --username ${POSTGRES_USER} <<-EOSQL
    CREATE ROLE superset SUPERUSER LOGIN PASSWORD 'superset';
    CREATE USER superset WITH ENCRYPTED PASSWORD 'superset';
    CREATE DATABASE superset;
    GRANT ALL PRIVILEGES ON DATABASE superset TO superset;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO superset;
    GRANT USAGE ON SCHEMA public TO superset;
    GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO superset;
EOSQL
    "
    # -----
    # iceberg catalog db initialization
    # -----
    ${DOCKER_COMPOSE} exec postgres /bin/bash -c "
PGPASSWORD=${POSTGRES_PASSWORD} psql --host postgres --username ${POSTGRES_USER} <<-EOSQL
    CREATE DATABASE ${ICEBERG_CATALOG_DB};
    GRANT ALL PRIVILEGES ON DATABASE iceberg TO ${POSTGRES_USER};
EOSQL
    "
    # start superset to initialize it later once it is up
    ${DOCKER_COMPOSE} up -d --force-recreate --no-deps --remove-orphans superset trino ${ICEBERG_CATALOG_SVC}
    # -----
    # prefect initialization
    # -----
    docker-compose exec postgres /bin/bash -c "
PGPASSWORD=${POSTGRES_PASSWORD} psql --host postgres --username ${POSTGRES_USER} <<-EOSQL
    CREATE DATABASE ${PREFECT_DATABASE};
    GRANT ALL PRIVILEGES ON DATABASE ${PREFECT_DATABASE} TO ${POSTGRES_USER};
EOSQL"
    ${DOCKER_COMPOSE} up -d --force-recreate --no-deps --remove-orphans prefect-server
    sleep 5
    docker-compose exec prefect-server /bin/bash -c "
        cd ${LAKEHOUSE_DATA_PATH}/pipelines;
        prefect --no-prompt work-pool create ${PREFECT_WORKER_POOL} --type process;
    "
    ${DOCKER_COMPOSE} up -d --force-recreate --no-deps --remove-orphans prefect-worker
    sleep 5
    docker-compose exec prefect-worker /bin/bash -c "
        cd ${LAKEHOUSE_DATA_PATH}/pipelines;
        prefect --no-prompt deploy --all;
    "
    # configure superset to use trino as database
    docker-compose exec prefect-worker /bin/bash -c "
        cd ${LAKEHOUSE_DATA_PATH}/scripts && python setup_superset_db.py;
    "
}

function start_lakehouse() {
    start_databases
    ${DOCKER_COMPOSE} up -d --force-recreate --no-deps \
                    minio \
                    ${ICEBERG_CATALOG_SVC} \
                    trino \
                    superset \
                    jupyter \
                    prefect-server \
                    prefect-worker
    sleep 1
}

function init_config() { 
    # iceberg catalog configs
    eval "echo \"$(cat ${PYICEBERG_CONFIG_TEMPLATE})\"" > ${VOLUMES_FOLDER}/config/pyiceberg.yaml
    # if [ "${ICEBERG_CATALOG}" = "nessie" ]; then
    #     cp ./config/spark-defaults.nessie.conf ${SPARK_DEFAULTS_CONFIG}
    # else
    #     cp ./config/spark-defaults.rest-catalog.conf ${SPARK_DEFAULTS_CONFIG}
    # fi
    # trino config
    eval "echo \"$(cat ./config/trino-catalog.template.properties)\"" > ${VOLUMES_FOLDER}/config/trino-catalog.properties
    # prefect pipelines config
    eval "echo \"$(cat ./data/pipelines/prefect.template.yaml)\"" > ./data/pipelines/prefect.yaml
}

function initialize() {
    echo "Environment needs to be initialized...."
    rm -rf ${VOLUMES_FOLDER} > /dev/null 2>&1
    mkdir -p ${VOLUMES_FOLDER}/config > /dev/null 2>&1
    init_config
    start_databases
    init_environment
    download_sample_dataset
    touch ${INITIALIZED_MARKER}
}

function ensure_images() {
    local superset_image_hash=$(docker images -q ${SUPERSET_IMAGE} 2> /dev/null)
    if [ -z "${superset_image_hash}" ]; then
        echo "building superset docker image ...";
        docker build \
            -f build/superset/Dockerfile -t ${SUPERSET_IMAGE} \
            --build-arg SUPERSET_BASE_IMAGE=${SUPERSET_BASE_IMAGE} build/superset
    fi
}

function start() {
    ensure_images
    if [ ! -d ${VOLUMES_FOLDER} ] || [ ! -f ${INITIALIZED_MARKER} ]; then
        initialize
    fi
    start_lakehouse
}

function stop() {
    ${DOCKER_COMPOSE} down
}


function status() {
    echo '-------------------------------'
    echo '      Lakehouse Status'
    echo '-------------------------------'
    ${DOCKER_COMPOSE} ps
    echo '-------------------------------'
}


function reset() {
    stop
    rm -rf ${VOLUMES_FOLDER}
}

function print_urls() {
    echo "--------------------------------------------" && \
	echo "           ENVIRONMENT LOCAL URLS " && \
	echo "--------------------------------------------" && \
	echo "   MinIO UI url:        http://localhost:9001  (admin/password)" && \
	echo "   Trino url:           http://localhost:8091"  && \
	echo "   Superset url:        http://localhost:8088  (admin/admin) (trino connection config trino://bla@trino:8080/sparkcognition)" && \
	echo "   Superset swagger:    http://localhost:8088/swagger/v1" && \
	echo "   Jupyter url:         http://localhost:5006"
}

# ------------------------------------


ROOT_FOLDER=$(dirname $0)
pushd ${ROOT_FOLDER} > /dev/null 2>&1

prepare_environment

case "$1" in
    "reset")
        stop
        reset
        ;;
    "restart")
        stop
        start
        ;;
    "start")
        start
        status
        print_urls
        ;;
    "status")
        status
        ;;
    "stop")
        stop
        ;;
    *)
        echo "Unknown option <$1>. Options: reset, start, stop, restart, status"
        exit 1
        ;;
esac

popd > /dev/null 2>&1