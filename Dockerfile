FROM ubuntu:22.04
WORKDIR /home/ec2-user
COPY . .
# Upgrade installed packages
RUN apt-get update && apt-get upgrade -y && apt-get clean

# (...)

# Python package management and basic dependencies
RUN apt-get install -y vim fish curl software-properties-common
RUN add-apt-repository ppa:deadsnakes/ppa && apt-get update
RUN apt-get install -y python3.10 python3.10-dev python3.10-distutils python3.10-venv python3-pip

# Register the version in alternatives
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1

# Set python 3 as the default python
RUN update-alternatives --set python3 /usr/bin/python3.10

# Install uv and use it to install requirements
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    PATH=$PATH:~/.local/bin:/root/.cargo/bin && \
    which uv && \
    uv pip install --system --no-cache -r requirements.txt

# Install Java
RUN apt-get install -y openjdk-11-jdk
