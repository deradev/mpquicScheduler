# Multipath-QUIC schedulers for video streaming applications.

This repository contains the sources of research work regarding Multipath-QUIC scheduling.
To this end the [Multipath-QUIC implementation from Q. Deconinck et al.](https://github.com/qdeconinck/mp-quic) was adapted and extended by new scheduler implementations.
Those schedulers are evaluated in a DASH video streaming scenario.
MP-QUIC was integrated into [Caddyserver](https://caddyserver.com/).
[AStream](https://github.com/pari685/AStream) serves as open-source DASH client.
AStream was also extended by using MP-QUIC as transport layer protocol.

All source code is targeted to run on Ubuntu 64 bit machines.

## Structure of this repository

Open source adaptations:
* [src/quic-go](https://github.com/deradev/mpquicScheduler/src/quic-go) contains extended MP-QUIC implementation written in Golang.
* [src/caddy](https://github.com/deradev/mpquicScheduler/src/caddy) contains Caddyserver with integrated MP-QUIC also written in Golang.
* [src/AStream](https://github.com/deradev/mpquicScheduler/src/AStream) contains DASH client with interchangeable Transport protocol written in Python 2.7.
Review adaptations:
The original repositories have not been integrated as recursive git modules but were copied instead.
Review changes by navigating into the corresponding subfolder and use **git diff**.

Own implementations:
* [src/dash/caddy](https://github.com/deradev/mpquicScheduler/src/dash/caddy) is used to build a Caddyserver executable with local MP-QUIC. 
* [src/dash/client/proxy_module](https://github.com/deradev/mpquicScheduler/src/dash/client/proxy_module) is a Python module that allows to issue http requests via local MP-QUIC.
Creating a Linux shared object (.so) allows bridging Go code into a Python module.

## Build

The Go code modules are build with Golang version 1.12.
Here used modules are build *outside* of GOPATH.
Herefore the local setup redirects their modular dependencies to the local implementations.

Build MP-QUIC:
```
cd src/quic-go
go build ./...
```
Notes: Go modules allow recursive build, this module must not necessarily be build explicitely.
The MP-QUIC module can be used by other Go modules via reference in their go.mod.

Build Caddy executable:
```
cd src/dash/caddy
go build
```

Build MP-QUIC shared object module:
```
cd src/dash/client/proxy_module
go build -o proxy_module.so -buildmode=c-shared proxy_module.go
```

## Use

### Prepare AStream DASH client
After building the proxy module, copy AStream dependencies.
(Probably required path change in line 5 of src/dash/client/proxy_module/conn.py)
```
cp src/dash/client/proxy_module/proxy_module.h src/AStream/dist/client/
cp src/dash/client/proxy_module/proxy_module.so src/AStream/dist/client/
cp src/dash/client/proxy_module/conn.py src/AStream/dist/client/
```

### Prepare Caddyserver
For DASH video streaming Caddy needs setup to serve video chunks.
A file named [*Caddyfile*](https://caddyserver.com/tutorial/caddyfile) must be configured to this end.
Example Caddyfile:
```
https://localhost:4242 {
    root <URL to DASH video files>
    tls self_signed
}
```

### Run Caddyserver
Execute the created ELF64 from src/dash/caddy:
```
# Run caddy on single path.
./caddy -quic
# Or run caddy with multipath and lowRTT scheduler.
# Possible schedulers [ lowRTT, RR, oppRedundant ], default is lowRTT.
./caddy -quic -mp -scheduler lowRTT
```

### Run AStream DASH client
Run the AStream client from src/AStream:
```
# Run AStream on single path.
python AStream/dist/client/dash_client.py -m <SERVER URL> -p 'basic' -q
# Or run caddy with multipath and lowRTT scheduler.
# Possible schedulers [ lowRTT, RR, oppRedundant ].
python AStream/dist/client/dash_client.py -m <SERVER URL> -p 'basic' -q -mp -s lowRTT
```

## References

This repository contains modified source code versions:
* [MP-QUIC](https://github.com/qdeconinck/mp-quic)
* [Caddyserver](https://github.com/caddyserver/caddy)
* [AStream](https://github.com/pari685/AStream)
