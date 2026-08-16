ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.20
FROM ${BUILD_FROM}

RUN apk add --no-cache \
    bluez \
    bluez-deprecated \
    bluez-libs \
    python3 \
    py3-pip

RUN pip3 install --no-cache-dir --break-system-packages \
    dbus-next==0.2.3 \
    paho-mqtt==2.1.0

COPY run.sh /run.sh
COPY bridge.py /bridge.py
RUN chmod 0755 /run.sh

CMD ["/run.sh"]
