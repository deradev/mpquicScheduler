#!/bin/bash


# Go build outside of GOPATH requires modular build from current working directory

cd src/quic-go
go build ./...

cd ../../src/dash/caddy
go build

cd ../../../src/dash/client/proxy_module
go build -o proxy_module.so -buildmode=c-shared proxy_module.go


# Copy python-go code bridge requirements

cd ../../../../
cp src/dash/client/proxy_module/proxy_module.h src/AStream/dist/client/
mv src/dash/client/proxy_module/proxy_module.so src/AStream/dist/client/
cp src/dash/client/proxy_module/conn.py src/AStream/dist/client/
