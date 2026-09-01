#!/bin/sh
# AEGIS container entrypoint. Delegates to the aegis CLI, defaulting to the
# probe command so the healthcheck and a bare `docker run` both do something
# sensible (there is no standalone web server yet; aegis is an execution
# library/worker).
set -eu

if [ "$#" -eq 0 ]; then
    set -- probe
fi

exec python -m aegis.cli "$@"
