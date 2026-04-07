FROM alpine:3.19

RUN apk add --no-cache \
    lua5.4 \
    lua5.4-dev \
    lua5.4-cjson \
    lua5.4-sec \
    && rm -rf /var/lib/apt/lists/*

RUN adduser -D -s /bin/false sandbox && chmod 1777 /tmp

COPY sandbox_runner.lua /sandbox_runner.lua

RUN sed -i 's/\r$//' /sandbox_runner.lua && \
    chmod +x /sandbox_runner.lua && \
    chown sandbox:sandbox /sandbox_runner.lua

USER sandbox

ENV LUA_SANDBOX_TIMEOUT=5

CMD ["lua5.4", "/sandbox_runner.lua"]