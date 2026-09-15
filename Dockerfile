FROM odoo:19.0

USER root

# Install system dependencies if required by any pip packages
RUN apt-get update && apt-get install -y \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /etc/odoo/requirements-oacis.txt

RUN pip3 install --no-cache-dir --break-system-packages --ignore-installed -r /etc/odoo/requirements-oacis.txt

# Bake all custom addons into the image so it is self-contained
COPY custom_addons /mnt/extra-addons
RUN chown -R odoo:odoo /mnt/extra-addons

# Bake the Odoo config used by docker-compose
COPY config/odoo-staging.conf /etc/odoo/odoo.conf
RUN chown odoo:odoo /etc/odoo/odoo.conf

USER odoo
