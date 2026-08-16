#!/usr/bin/with-contenv bash
set -e
export SUPERVISOR_API="http://172.30.32.2"
export CACHE_DIR="/run/bashio"
source /usr/lib/bashio/bashio.sh
export MQTT_HOST="$(bashio::config mqtt_host)"
export MQTT_PORT="$(bashio::config mqtt_port)"
export MQTT_USER="$(bashio::services mqtt username)"
export MQTT_PASSWORD="$(bashio::services mqtt password)"
exec python3 /bridge.py
