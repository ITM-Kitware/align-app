FROM kitware/trame:uv-cuda

USER root
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Copy setup configuration
COPY --chown=trame-user:trame-user bundles/docker/setup /deploy/setup

# Copy the align-app package source
COPY --chown=trame-user:trame-user align_app /deploy/align_app
COPY --chown=trame-user:trame-user pyproject.toml /deploy/pyproject.toml
COPY --chown=trame-user:trame-user README.md /deploy/README.md

RUN /opt/trame/entrypoint.sh build
