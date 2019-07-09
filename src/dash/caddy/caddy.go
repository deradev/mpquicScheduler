package main

import (
	// This import is redirected in the go.mod file to use the local implementation.
	"github.com/mholt/caddy/caddy/caddymain"
)

func main() {
	// Nothing interesting here: setup and start running Caddy.
	caddymain.EnableTelemetry = false
	caddymain.Run()
}
