ARG INGESTION_BASE_IMAGE
FROM ${INGESTION_BASE_IMAGE}

# RUN apt-get update && apt-get install -y vim ca-certificates git-all && \
#     python -m pip install --upgrade pip
COPY ./data/pipelines/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt