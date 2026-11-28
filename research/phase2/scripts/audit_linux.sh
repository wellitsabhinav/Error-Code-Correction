#!/usr/bin/env bash
# Read-only inventory of the existing public toolchain; no installs or cleanup.
set +e
df -h
df -i
du -sh /opt /usr/local ~/.cache /var/cache/apt 2>/dev/null
command -v git python3 yosys iverilog vvp sta openroad docker
docker images --format '{{.Repository}}:{{.Tag}} {{.Size}}'
docker volume ls
docker system df
docker image inspect $(docker images -q) --format '{{.Id}} {{json .RepoDigests}}'
