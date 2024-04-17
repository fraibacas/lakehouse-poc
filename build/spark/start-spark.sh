#!/bin/bash
. "/opt/spark/bin/load-spark-env.sh"


mkdir -p /tmp/spark-events

function start_master() {
    echo "starting spark master..."
    export SPARK_MASTER_HOST=`hostname`
    cd /opt/spark/bin && \
        ./spark-class org.apache.spark.deploy.master.Master \
            --ip $SPARK_MASTER_HOST \
            --port $SPARK_MASTER_PORT \
            --webui-port $SPARK_MASTER_WEBUI_PORT >> $SPARK_MASTER_LOG &
    start_history_server
    start_spark_connect
}

function start_worker() {
    echo "starting spark worker..."
    cd /opt/spark/bin && \
        ./spark-class org.apache.spark.deploy.worker.Worker --webui-port $SPARK_WORKER_WEBUI_PORT $SPARK_MASTER >> $SPARK_WORKER_LOG &
}

function start_history_server() {
    cd /opt/spark/sbin && start-history-server.sh &
}

function start_spark_connect() {
    echo "wip"
    #cd /opt/spark/sbin && ./start-connect-server.sh --packages org.apache.spark:spark-connect_2.12:3.4.0
}

if [ "$SPARK_WORKLOAD" == "master" ]; then
    start_master
    tail -f $SPARK_MASTER_LOG
elif [ "$SPARK_WORKLOAD" == "worker" ]; then
    start_worker
    tail -f $SPARK_WORKER_LOG
elif [ "$SPARK_WORKLOAD" == "standalone" ];
then
    start_master
    start_worker
    tail -f $SPARK_MASTER_LOG $SPARK_WORKER_LOG
else
    echo "Undefined Workload Type $SPARK_WORKLOAD, must specify: master, worker, submit"
fi