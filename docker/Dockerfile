# yolka — agent workspace image
# A self-contained Linux environment with the essential toolchain for the
# hybrid DevOps/network/software engineer persona. Hermes itself runs on the
# host or in the official nousresearch/hermes-agent image; this image is the
# *workspace* yolka operates in (terminal backend / ssh target / CI runner).
#
# Build:   docker build -t yolka:latest .
# Run:     docker run --rm -it yolka:latest bash
#          (or wire it as a Hermes terminal backend — see README.md §Docker)

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC

# ---------- base toolchain ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
    # essentials
    bash bash-completion ca-certificates curl wget git git-lfs jq unzip zip \
    gnupg lsb-release software-properties-common apt-transport-https \
    openssh-client sshpass rsync vim nano less \
    # build toolchain
    build-essential gcc g++ make cmake pkg-config \
    python3 python3-venv python3-pip python3-dev \
    nodejs npm \
    # network / ops debugging
    netcat-openbsd dnsutils iputils-ping iproute2 traceroute tcpdump \
    whois ldnsutils \
    # PDF / docs / RTL (yolka's software-engineering domain)
    poppler-utils libpoppler-dev libharfbuzz-dev libfribidi-dev \
    fonts-noto fonts-noto-arabic tesseract-ocr tesseract-ocr-fas \
    libreoffice-writer \
    # observability
    htop procps sysstat lsof strace \
    && rm -rf /var/lib/apt/lists/*

# ---------- Python automation stack ----------
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir \
    # network automation
    ansible-core netmiko nornir scrapli napalm \
    # dev / ops
    requests httpx python-dotenv pyyaml jinja2 paramiko \
    # PDF / docs
    pymupdf reportlab arabic-reshaper python-bidi \
    # data
    pandas openpyxl \
    && ln -s /opt/venv/bin/* /usr/local/bin/ 2>/dev/null || true

ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV=/opt/venv

# ---------- user & workspace ----------
RUN useradd -m -s /bin/bash agent \
    && mkdir -p /workspace /home/agent/.hermes \
    && chown -R agent:agent /workspace /home/agent

WORKDIR /workspace
USER agent

# Identity goes here (bind-mount from the host, never baked in):
#   -v $HOME/.hermes:/home/agent/.hermes
#   -v $(pwd)/../SOUL.md:/home/agent/.hermes/SOUL.md:ro   (optional, read-only)
#
# Health probe: verifies the workspace and python stack are usable.
HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
  CMD bash -c "test -w /workspace && python3 -c 'import requests, netmiko' && echo ok"

CMD ["bash"]
