ARG SPARK_BASE_IMAGE
FROM ${SPARK_BASE_IMAGE}

USER root

ARG ICEBERG_JAR_URL
ARG ICEBERG_JAR
ARG ICEBERG_S3_JAR_URL
ARG ICEBERG_S3_JAR

COPY requirements.txt /tmp/requirements.txt

RUN update-alternatives --install "/usr/bin/python" "python" "$(which python3)" 1 \
    && apt update && apt install -y libffi-dev rsync \
    && mkdir /home/spark \
    && chown -R spark:spark /opt/spark /home/spark

RUN pip install -r /tmp/requirements.txt

# Download iceberg spark runtime
RUN curl -s ${ICEBERG_JAR_URL} -Lo /opt/spark/jars/${ICEBERG_JAR} && \
    curl -s ${ICEBERG_S3_JAR_URL} -Lo /opt/spark/jars/${ICEBERG_S3_JAR}

COPY start-spark.sh /opt/spark/

ENV SPARK_HOME=/opt/spark \
    PYTHONHASHSEED=1 \
    SPARK_MASTER_PORT=7077 \
    SPARK_MASTER_WEBUI_PORT=8080 \
    SPARK_LOG_DIR=/opt/spark/logs \
    SPARK_MASTER_LOG=/opt/spark/logs/spark-master.out \
    SPARK_WORKER_LOG=/opt/spark/logs/spark-worker.out \
    SPARK_WORKER_WEBUI_PORT=8080 \
    SPARK_WORKER_PORT=7000 \
    SPARK_MASTER="spark://spark-master:7077" \
    SPARK_WORKLOAD="master"

WORKDIR /opt/spark
EXPOSE 8080 7077 6066

RUN chmod +x start-spark.sh && \
    mkdir -p $SPARK_LOG_DIR && \
    touch $SPARK_MASTER_LOG && \
    touch $SPARK_WORKER_LOG && \
    ln -sf /dev/stdout $SPARK_MASTER_LOG && \
    ln -sf /dev/stdout $SPARK_WORKER_LOG && \
    export PATH=${PATH}:/home/spark/.local/bin

CMD ["/bin/bash", "start-spark.sh"]