# Multipath-QUIC schedulers for video streaming applications.

This repository contains the sources of research work regarding Multipath-QUIC scheduling.
[Multipath-QUIC from Q. Deconinck et al.](https://github.com/qdeconinck/mp-quic) is a Golang implementation of Multipath-QUIC.
It was initially forked from quic-go (https://github.com/lucas-clemente/quic-go).
Additional scheduler implementations are added in this work.

These schedulers are evaluated in a DASH video streaming scenario:
[Caddyserver](https://caddyserver.com/) is a open source Http server written in Golang making it easy to integrate MP-QUIC.
[AStream](https://github.com/pari685/AStream) serves as open-source DASH client.
AStream was also extended by using MP-QUIC as transport layer protocol.

All source code is targeted to run on Ubuntu 64-bit machines.

## Structure of this repository

Open source adaptations:
* [src/quic-go](https://github.com/deradev/mpquicScheduler/tree/master/src/quic-go) contains extended MP-QUIC implementation written in Golang.
* [src/caddy](https://github.com/deradev/mpquicScheduler/tree/master/src/caddy) contains Caddyserver with integrated MP-QUIC also written in Golang.
* [src/AStream](https://github.com/deradev/mpquicScheduler/tree/master/src/AStream) contains DASH client with interchangeable Transport protocol written in Python 2.7.

Review adaptations:
The original repositories have not been integrated as recursive git modules but were copied instead.
Review changes by navigating into the corresponding subfolder and using **git diff**.

Original implementations:
* [src/dash/caddy](https://github.com/deradev/mpquicScheduler/tree/master/src/dash/caddy) is used to build a Caddyserver executable with local MP-QUIC. 
* [src/dash/client/proxy_module](https://github.com/deradev/mpquicScheduler/tree/master/src/dash/client/proxy_module) is a Python module that allows to issue http requests via local MP-QUIC.
Creating a Linux shared object (.so) allows bridging Go code into a Python module.

Example video setup:
* [example/video/big-buck-bunny](https://github.com/deradev/mpquicScheduler/tree/master/example/video/big-buck-bunny) contains a DASH-streamable video and a corresponding sample Caddyserver configuration file. The edited video resource is 'Big Buck Bunny' (c) copyright 2008, Blender Foundation / www.bigbuckbunny.org.

## Quickstart (stream the *Big Buck Bunny* sample movie)
```
# Clone repository and build sources
git clone https://github.com/deradev/mpquicScheduler
cd mpquicScheduler
./build.sh

# Run Caddyserver with sample Caddyfile and Multipath-QUIC
./src/dash/caddy/caddy -conf example/Caddyfile -quic -mp
# Run AStream client with sample video target and Multipath-QUIC
python src/AStream/dist/client/dash_client.py -m "https://localhost:4242/big-buck-bunny/output_dash.mpd" -p 'basic' -q -mp
```

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

Build Caddyserver executable:
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
(Probably also requires path change in line 5 of src/dash/client/proxy_module/conn.py)
```
cp src/dash/client/proxy_module/proxy_module.h src/AStream/dist/client/
cp src/dash/client/proxy_module/proxy_module.so src/AStream/dist/client/
cp src/dash/client/proxy_module/conn.py src/AStream/dist/client/
```

#### Prepare Caddyserver
For DASH video streaming Caddyserver needs setup to serve video chunks.
A file named [*Caddyfile*](https://caddyserver.com/tutorial/caddyfile) must be configured to this end.
Example Caddyfile:
```
https://localhost:4242 {
    root <URL to DASH video files>
    tls self_signed
}
```

#### Run Caddyserver
Run the created executable from src/dash/caddy:
```
# Run Caddyserver on single path.
./caddy -quic
# Or run caddy with multipath and lowRTT scheduler.
# Possible schedulers [ lowRTT, RR, oppRedundant, utilRepair ] default is lowRTT.
./caddy -quic -mp -scheduler lowRTT
```

#### Run AStream DASH client
Run the AStream client from src/AStream:
```
# Run AStream on single path.
python AStream/dist/client/dash_client.py -m <SERVER URL TO MPD> -p 'basic' -q
# Or run caddy with multipath and lowRTT scheduler.
# Possible schedulers [ lowRTT, RR, oppRedundant ].
python AStream/dist/client/dash_client.py -m <SERVER URL TO MPD> -p 'basic' -q -mp -s lowRTT
```

## References

This repository contains modified source code versions:
* [MP-QUIC](https://github.com/qdeconinck/mp-quic)
* [Caddyserver](https://github.com/caddyserver/caddy)
* [AStream](https://github.com/pari685/AStream)

This repository contains a cut version of the 'Big Buck Bunny' cinematic by the Blender Foundation:
* [Big Buck Bunny](https://peach.blender.org/download/) (c) copyright 2008, Blender Foundation / www.bigbuckbunny.org
