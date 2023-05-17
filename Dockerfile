FROM ubuntu:jammy

LABEL org.opencontainers.image.authors="steven@byoda.org"

# TODO
# 1: run uvicorn/fastapi/app as non-root user
# 2: use nginx from Nginx Inc docker repo
# 3: optimize for size

ENV DEBIAN_FRONTEND noninteractive
ENV LANG=C.UTF-8
WORKDIR /opt/byoda

HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD curl --fail http://localhost:8000/api/v1/status || exit 1

# RUN apt-get update && apt-get install -y --no-install-recommends \
RUN apt-get update && apt-get install -y \
        curl \
        ca-certificates \
        build-essential \
        python3 \
        python3-distutils \
        libssl-dev \
        libffi-dev \
        python3-dev \
        libpq-dev \
        nginx \
        sqlite3 \
        libaugeas0 \
        bind9-dnsutils \
        mtr-tiny \
        net-tools \
        netcat \
    && apt-get -y clean \
    && rm -rf /var/lib/apt/lists/*

RUN curl -s https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py && \
        python3 /tmp/get-pip.py && \
        rm /tmp/get-pip.py && \
        python3 -m pip install setuptools==59.8.0 && \
        python3 -m pip install pipenv && \
        python3 -m pip cache purge

# We've compiled nginx with modules such as njs
COPY --from=build nginx-1.25/nginx /usr/sbin
RUN chmod 755 /usr/sbin/nginx

COPY --from=build \
        nginx-1.25/ngx_http_brotli_filter_module.so \
        nginx-1.25/ngx_http_brotli_static_module.so \
        nginx-1.25/ngx_http_geoip2_module.so \
        nginx-1.25/ngx_http_hmac_secure_link_module.so \
        nginx-1.25/ngx_http_js_module.so \
        /usr/share/nginx/modules/

COPY cdn-server/files/dhparam.pem /etc/nginx/ssl/
RUN openssl rand 80 >/etc/nginx/ssl/sslticket.key
COPY cdn-server/files/nginx.conf /etc/nginx/
COPY cdn-server/files/virtualserver.conf /etc/nginx/conf.d/
COPY cdn-server/files/50x.html /usr/share/nginx/html/

###
### Byoda bits
###
RUN mkdir -p \
    /var/log/byoda \
    byoda-cdn \
    /etc/nginx/ssl \
    /var/log/nginx \
    /var/cache/nginx/{proxy_temp,objectstorage} \
    /opt/byoda/keys

COPY ./Pipfile ./Pipfile.lock byoda-cdn/
RUN cd /opt/byoda/byoda-cdn && pipenv install --deploy --ignore-pipfile && pipenv clean

ENV PYTHONPATH=/podserver/byoda-cdn

COPY cdn-server/files/startup.sh .

COPY . /opt/byoda/byoda-cdn/

CMD "/opt/byoda/startup.sh"
