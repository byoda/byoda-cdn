#!/bin/bash

export PYTHONPATH=$PYTHONPATH:/opt/byoda/byoda-cdn

cd /opt/byoda/byoda-cdn

FAILURE=

# Start nginx first
echo "Starting nginx"
nginx

if [[ "$?" != "0" ]]; then
    echo "Nginx failed to start"
    FAILURE=1
fi

if [[ -z "${FAILURE}" ]]; then
    # location of pid file is used by byoda.util.reload.reload_gunicorn
    rm -rf /run/cdn-server.pid
    echo "Starting the CDN server"
    pipenv run python3 -m gunicorn -p /run/cdn-server.pid --error-logfile /var/log/byoda/gunicorn-error.log --access-logfile /var/log/byoda/gunicorn-access.log -c gunicorn.conf.py cdn-server.main:app
    if [[ "$?" != "0" ]]; then
        echo "Failed to start the application server"
        FAILURE=1
    fi
fi

# Wait for 15 minutes if we crash while running in DEBUG mode
# so the owner of the pod can check the logs
if [[ "${FAILURE}" != "0" && -n "${DEBUG}" ]]; then
    echo "Failed, sleeping 900 seconds"
    sleep 900
fi
