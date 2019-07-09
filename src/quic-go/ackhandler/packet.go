package ackhandler

import (
	"time"

	"github.com/lucas-clemente/quic-go/internal/protocol"
	"github.com/lucas-clemente/quic-go/internal/wire"
)

// A Packet is a packet
// +gen linkedlist
type Packet struct {
	PacketNumber    protocol.PacketNumber
	Frames          []wire.Frame
	Length          protocol.ByteCount
	EncryptionLevel protocol.EncryptionLevel

	SendTime time.Time
}

// GetFramesForRetransmission gets all the frames for retransmission
func (p *Packet) GetFramesForRetransmission() []wire.Frame {
	var fs []wire.Frame
	for _, frame := range p.Frames {
		switch frame.(type) {
		case *wire.AckFrame:
			continue
		case *wire.StopWaitingFrame:
			continue
		}
		fs = append(fs, frame)
	}
	return fs
}

func (p *Packet) IsRetransmittable() bool {
	for _, f := range p.Frames {
		switch f.(type) {
		case *wire.StreamFrame:
			return true
		case *wire.RstStreamFrame:
			return true
		case *wire.WindowUpdateFrame:
			return true
		case *wire.BlockedFrame:
			return true
		case *wire.PingFrame:
			return true
		case *wire.GoawayFrame:
			return true
		case *wire.AddAddressFrame:
			return true
		case *wire.PathsFrame:
			return true
		}
	}
	return false
}

// GetStreamFrameLength returns the length of contained Stream frames payload
func (p *Packet) GetStreamFrameLength() uint64 {

	var sfPayloadLength uint64

	for _, f := range p.Frames {
		switch f.(type) {
		case *wire.StreamFrame:
			// DataLen() gives the payload length of the stream frame without header
			sfPayloadLength += uint64(f.(*wire.StreamFrame).DataLen())
		}
	}

	return sfPayloadLength
}

// GetCopyFrames returns a slice with all contained frames that can be duplicated
func (p *Packet) GetCopyFrames() []wire.Frame {

	copyFrames := make([]wire.Frame, 0)

	for _, f := range p.Frames {
		// Frames suitable for MP-duplication
		switch f.(type) {
		case *wire.StreamFrame:
			copyFrames = append(copyFrames, f)
		case *wire.RstStreamFrame:
			copyFrames = append(copyFrames, f)
		case *wire.WindowUpdateFrame:
			copyFrames = append(copyFrames, f)
		case *wire.BlockedFrame:
			copyFrames = append(copyFrames, f)
		case *wire.PingFrame:
			copyFrames = append(copyFrames, f)
		case *wire.AddAddressFrame:
			copyFrames = append(copyFrames, f)
		case *wire.PathsFrame:
			copyFrames = append(copyFrames, f)
		case *wire.GoawayFrame:
			copyFrames = append(copyFrames, f)
		}
	}

	if len(copyFrames) == 0 {
		return nil
	}
	return copyFrames
}

// IsDupDropable returns a slice with all contained frames that can be duplicated
func (p *Packet) IsDupDropable() bool {

	for _, f := range p.Frames {
		// Frames suitable for MP-duplication
		switch f.(type) {
		case *wire.StreamFrame:
			continue
		case *wire.RstStreamFrame:
			continue
		case *wire.WindowUpdateFrame:
			continue
		case *wire.BlockedFrame:
			continue
		case *wire.PingFrame:
			continue
		case *wire.AddAddressFrame:
			continue
		case *wire.PathsFrame:
			continue
		case *wire.GoawayFrame:
			continue
		default:
			return false
		}
	}

	return true
}
