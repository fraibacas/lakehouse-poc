ARG SUPERSET_BASE_IMAGE
FROM ${SUPERSET_BASE_IMAGE}

ENV SUPERSET_BASE_IMAGE=${SUPERSET_BASE_IMAGE}

# Switching to root to install the required packages
USER root
RUN pip install psycopg2 trino elasticsearch-dbapi

COPY superset-init.sh /app

USER superset
ENTRYPOINT [ "/app/superset-init.sh" ]