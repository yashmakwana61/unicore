FROM odoo:19.0

USER root

# Install system dependencies if required by any pip packages
RUN apt-get update && apt-get install -y \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /etc/odoo/requirements-oacis.txt

RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed -r /etc/odoo/requirements-oacis.txt

USER odoo
