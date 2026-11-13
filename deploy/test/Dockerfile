# A throwaway Ubuntu 24.04 machine with real systemd, used only to test the
# hardening scripts (see deploy/test-hardening.sh). Never deployed.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      systemd systemd-sysv dbus iproute2 iptables openssh-client openssh-server sudo curl ca-certificates python3 less \
 && rm -rf /var/lib/apt/lists/*
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
