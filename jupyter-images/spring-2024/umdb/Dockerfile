# Heavily borrowed from docker-stacks
# https://raw.githubusercontent.com/jupyter/docker-stacks/main/images/docker-stacks-foundation/Dockerfile
ARG BASE_CONTAINER=nvcr.io/nvidia/tensorflow:24.01-tf2-py3
FROM $BASE_CONTAINER

LABEL maintainer="Unidata <support-gateway@unidata.ucar.edu>"
ARG NB_USER="jovyan"
ARG NB_UID="1000"
ARG NB_GID="100"

# Fix: https://github.com/hadolint/hadolint/wiki/DL4006
# Fix: https://github.com/koalaman/shellcheck/wiki/SC3014
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

USER root

ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update --yes && \
    apt-get upgrade --yes && \
    apt-get install --yes --no-install-recommends \
    bzip2  ca-certificates locales sudo wget software-properties-common \
    libproj-dev proj-data proj-bin libgeos-dev && \
    python3 -m pip install --no-cache-dir \
    absl-py \
    black>=22 \
    bokeh \
    build \
    dask \
    datasets \
    dm-tree \
    flake8 \
    google \
    h5py \
    ipywidgets \
    isort \
    jax[cpu] \
    jupyter-server-proxy \
    jupyter_server \
    jupyter_server_terminals \
    jupyterhub \
    jupyterlab \
    jupyterlab_widgets \
    keras \
    keras-tuner \
    matplotlib \
    namex \
    nbgitpuller \
    netcdf4 \
    notebook \
    numpy \
    optuna \
    pandas \
    protobuf \
    pytest \
    pytest-cov \
    requests \
    rich \
    rouge-score \
    scikit-learn \
    scipy \
    sentencepiece \
    shapely \
    tensorboard-plugin-profile \
    tf-nightly[and-cuda] \
    torch \
    torchaudio \
    torchvision \
    transformers \
    visualkeras \
    xarray \
    --upgrade && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen

# Configure environment
ENV SHELL=/bin/bash \
    NB_USER="${NB_USER}" \
    NB_UID=${NB_UID} \
    NB_GID=${NB_GID} \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    LANGUAGE=C.UTF-8 \
    HOME="/home/${NB_USER}"

COPY fix-permissions /usr/local/bin/fix-permissions
RUN chmod a+rx /usr/local/bin/fix-permissions

# Enable prompt color in the skeleton .bashrc before creating the default NB_USER
# hadolint ignore=SC2016
RUN sed -i 's/^#force_color_prompt=yes/force_color_prompt=yes/' /etc/skel/.bashrc

# Create NB_USER with name jovyan user with UID=1000 and in the 'users' group
# and make sure these dirs are writable by the `users` group.
RUN echo "auth requisite pam_deny.so" >> /etc/pam.d/su && \
    sed -i.bak -e 's/^%admin/#%admin/' /etc/sudoers && \
    sed -i.bak -e 's/^%sudo/#%sudo/' /etc/sudoers && \
    useradd --no-log-init --create-home --shell /bin/bash --uid "${NB_UID}" --no-user-group "${NB_USER}" && \
    chmod g+w /etc/passwd && \
    fix-permissions "${HOME}"

COPY Acknowledgements.ipynb /

USER ${NB_UID}

WORKDIR "${HOME}"
