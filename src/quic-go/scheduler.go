package quic

import (
	"os"
	"strconv"
	"time"

	"github.com/lucas-clemente/quic-go/ackhandler"
	"github.com/lucas-clemente/quic-go/internal/protocol"
	"github.com/lucas-clemente/quic-go/internal/utils"
	"github.com/lucas-clemente/quic-go/internal/wire"
)

var (
	// SchedulerAlgorithm is the algorithm for packet -> path scheduling
	SchedulerAlgorithm string
	// LogPayload indicates if send goodput Bytes should be logged to file
	LogPayload = true
	// CongestionControl can be set to 'cubic', default is OLIA
	CongestionControl string
)

// SetSchedulerAlgorithm is used to adapt the scheduler
func SetSchedulerAlgorithm(scheduler string) {
	s := make([]byte, len(scheduler))
	copy(s, scheduler)
	SchedulerAlgorithm = string(s)
}

// SetCongestionControl is used to set the CC algorithm
func SetCongestionControl(cc string) {
	s := make([]byte, len(cc))
	copy(s, cc)
	CongestionControl = string(s)
}

// Identifier for a packet across paths
type dupID struct {
	PathID       protocol.PathID
	PacketNumber protocol.PacketNumber
}

type scheduler struct {
	// XXX Currently round-robin based, inspired from MPTCP scheduler
	quotas map[protocol.PathID]uint

	pathsRef *map[protocol.PathID]*path
	// Map duplicated Packets for selective drop
	dupPackets               map[dupID]dupID
	duplicatedPackets        uint64
	droppedDuplicatedPackets uint64

	// allSntBytes counts the total sent Bytes
	allSntBytes uint64
	// duplicatedStreamBytes counts the goodput Bytes that were duplicated
	duplicatedStreamBytes uint64

	// logStartTS is used to create relative stamps to avoid unsynched clock blur over all paths
	logStartTS    int64
	logFiles      map[protocol.PathID]*os.File
	lastSentBytes map[protocol.PathID]uint64
	lastLogTS     float64
}

func (sch *scheduler) setup() {
	sch.quotas = make(map[protocol.PathID]uint)
	sch.dupPackets = make(map[dupID]dupID)
}

func (sch *scheduler) getRetransmission(s *session) (hasRetransmission bool, retransmitPacket *ackhandler.Packet, pth *path) {
	// check for retransmissions first
	for {
		// TODO add ability to reinject on another path
		// XXX We need to check on ALL paths if any packet should be first retransmitted
		s.pathsLock.RLock()
	retransmitLoop:
		for _, pthTmp := range s.paths {
			retransmitPacket = pthTmp.sentPacketHandler.DequeuePacketForRetransmission()
			if retransmitPacket != nil {
				pth = pthTmp
				break retransmitLoop
			}
		}
		s.pathsLock.RUnlock()
		if retransmitPacket == nil {
			break
		}
		hasRetransmission = true

		if retransmitPacket.EncryptionLevel != protocol.EncryptionForwardSecure {
			if s.handshakeComplete {
				// Don't retransmit handshake packets when the handshake is complete
				continue
			}
			utils.Debugf("\tDequeueing handshake retransmission for packet 0x%x", retransmitPacket.PacketNumber)
			return
		}
		utils.Debugf("\tDequeueing retransmission of packet 0x%x from path %d", retransmitPacket.PacketNumber, pth.pathID)
		// resend the frames that were in the packet
		for _, frame := range retransmitPacket.GetFramesForRetransmission() {
			switch f := frame.(type) {
			case *wire.StreamFrame:
				s.streamFramer.AddFrameForRetransmission(f)
			case *wire.WindowUpdateFrame:
				// only retransmit WindowUpdates if the stream is not yet closed and the we haven't sent another WindowUpdate with a higher ByteOffset for the stream
				// XXX Should it be adapted to multiple paths?
				currentOffset, err := s.flowControlManager.GetReceiveWindow(f.StreamID)
				if err == nil && f.ByteOffset >= currentOffset {
					s.packer.QueueControlFrame(f, pth)
				}
			case *wire.PathsFrame:
				// Schedule a new PATHS frame to send
				s.schedulePathsFrame()
			default:
				s.packer.QueueControlFrame(frame, pth)
			}
		}
	}
	return
}

func (sch *scheduler) selectPathRoundRobin(s *session, hasRetransmission bool, hasStreamRetransmission bool, fromPth *path) *path {
	if sch.quotas == nil {
		sch.setup()
	}

	// TODO cope with decreasing number of paths (needed?)
	var selectedPath *path
	var lowerQuota, currentQuota uint
	var ok bool

	// Max possible value for lowerQuota at the beginning
	lowerQuota = ^uint(0)

pathLoop:
	for pathID, pth := range s.paths {
		// Don't block path usage if we retransmit, even on another path
		if !hasRetransmission && !pth.SendingAllowed() {
			continue pathLoop
		}

		// If this path is potentially failed, do no consider it for sending
		if pth.potentiallyFailed.Get() {
			continue pathLoop
		}

		// XXX Prevent using initial pathID if multiple paths
		if pathID == protocol.InitialPathID {
			continue pathLoop
		}

		currentQuota, ok = sch.quotas[pathID]
		if !ok {
			sch.quotas[pathID] = 0
			currentQuota = 0
		}

		if currentQuota < lowerQuota {
			selectedPath = pth
			lowerQuota = currentQuota
		}
	}

	return selectedPath

}

func (sch *scheduler) selectPathLowLatency(s *session, hasRetransmission bool, hasStreamRetransmission bool, fromPth *path) *path {

	var selectedPath *path
	var lowerRTT time.Duration
	var currentRTT time.Duration
	selectedPathID := protocol.PathID(255)

pathLoop:
	for pathID, pth := range s.paths {
		// Don't block path usage if we retransmit, even on another path
		// DERA: Only consider paths, that have space in their cwnd for 'new' packets.
		//			 Or consider all valid paths for outstanding retransmissions.
		if !hasRetransmission && !pth.SendingAllowed() {
			continue pathLoop
		}

		// If this path is potentially failed, do not consider it for sending
		if pth.potentiallyFailed.Get() {
			continue pathLoop
		}

		// XXX Prevent using initial pathID if multiple paths
		if pathID == protocol.InitialPathID {
			continue pathLoop
		}

		currentRTT = pth.rttStats.SmoothedRTT()

		// Prefer staying single-path if not blocked by current path
		// Don't consider this sample if the smoothed RTT is 0
		if lowerRTT != 0 && currentRTT == 0 {
			continue pathLoop
		}

		// Case if we have multiple paths unprobed
		if currentRTT == 0 {
			currentQuota, ok := sch.quotas[pathID]
			if !ok {
				sch.quotas[pathID] = 0
				currentQuota = 0
			}
			lowerQuota, _ := sch.quotas[selectedPathID]
			if selectedPath != nil && currentQuota > lowerQuota {
				continue pathLoop
			}
		}

		if currentRTT != 0 && lowerRTT != 0 && selectedPath != nil && currentRTT >= lowerRTT {
			continue pathLoop
		}

		// Update
		lowerRTT = currentRTT
		selectedPath = pth
		selectedPathID = pathID
	}

	return selectedPath
}

func (sch *scheduler) selectPathHighBW(s *session, hasRetransmission bool, hasStreamRetransmission bool, fromPth *path) *path {

	var selectedPath *path
	var higherBW float64
	var currentBW float64
	selectedPathID := protocol.PathID(255)

pathLoop:
	for pathID, pth := range s.paths {
		// Don't block path usage if we retransmit, even on another path
		// DERA: Only consider paths, that have space in their cwnd for 'new' packets.
		//			 Or consider all valid paths for outstanding retransmissions.
		if !hasRetransmission && !pth.SendingAllowed() {
			continue pathLoop
		}

		// If this path is potentially failed, do not consider it for sending
		if pth.potentiallyFailed.Get() {
			continue pathLoop
		}

		// XXX Prevent using initial pathID if multiple paths
		if pathID == protocol.InitialPathID {
			continue pathLoop
		}

		// Only use until the first smoothed RTT measurement is available
		if pth.rttStats.SmoothedRTT().Seconds() > 0 {
			currentBW = float64(pth.sentPacketHandler.GetCongestionWindow()) / pth.rttStats.SmoothedRTT().Seconds()
		}

		// Prefer staying single-path if not blocked by current path
		// Don't consider this sample if the smoothed RTT is 0
		if higherBW != 0 && currentBW == 0 {
			continue pathLoop
		}

		// Case if we have multiple paths unprobed
		if currentBW == 0 {
			currentQuota, ok := sch.quotas[pathID]
			if !ok {
				sch.quotas[pathID] = 0
				currentQuota = 0
			}
			lowerQuota, _ := sch.quotas[selectedPathID]
			if selectedPath != nil && currentQuota > lowerQuota {
				continue pathLoop
			}
		}

		if currentBW != 0 && higherBW != 0 && selectedPath != nil && currentBW < higherBW {
			continue pathLoop
		}

		// Update
		higherBW = currentBW
		selectedPath = pth
		selectedPathID = pathID
	}

	return selectedPath
}

// Select first path, that allows sending.
func (sch *scheduler) selectFreePath(s *session, hasRetransmission bool, hasStreamRetransmission bool, fromPth *path) *path {

pathLoop:
	for pathID, pth := range s.paths {
		// Don't block path usage if we retransmit, even on another path
		// DERA: Only consider paths, that have space in their cwnd for 'new' packets.
		//			 Or consider all valid paths for outstanding retransmissions.
		if !hasRetransmission && !pth.SendingAllowed() {
			continue pathLoop
		}

		// If this path is potentially failed, do no consider it for sending
		if pth.potentiallyFailed.Get() {
			continue pathLoop
		}

		// XXX Prevent using initial pathID if multiple paths
		if pathID == protocol.InitialPathID {
			continue pathLoop
		}

		return pth
	}

	return nil
}

// Select all paths for retransmission, or paths with space for new transmissions.
func (sch *scheduler) selectRedundantPaths(s *session, hasRetransmission bool, hasStreamRetransmission bool, fromPth *path) []*path {

	var selectedPaths []*path

pathLoop:
	for pathID, pth := range s.paths {
		// Don't block path usage if we retransmit, even on another path
		if !hasRetransmission && !pth.SendingAllowed() {
			continue pathLoop
		}

		// If this path is potentially failed, do no consider it for sending
		if pth.potentiallyFailed.Get() {
			continue pathLoop
		}

		// XXX Prevent using initial pathID if multiple paths
		if pathID == protocol.InitialPathID {
			continue pathLoop
		}

		selectedPaths = append(selectedPaths, pth)
	}

	return selectedPaths
}

// Exclude initial path from selection and discovery of new paths.
func (sch *scheduler) selectInitialPath(s *session, hasRetransmission bool, hasStreamRetransmission bool, fromPth *path) *path {

	// XXX Avoid using PathID 0 if there is more than 1 path
	if len(s.paths) <= 1 {
		if !hasRetransmission && !s.paths[protocol.InitialPathID].SendingAllowed() {
			return nil
		}
		return s.paths[protocol.InitialPathID]
	}

	// FIXME Only works at the beginning... Cope with new paths during the connection
	if hasRetransmission && hasStreamRetransmission && fromPth.rttStats.SmoothedRTT() == 0 {
		// Is there any other path with a lower number of packet sent?
		currentQuota := sch.quotas[fromPth.pathID]
		for pathID, pth := range s.paths {
			if pathID == protocol.InitialPathID || pathID == fromPth.pathID {
				continue
			}
			// The congestion window was checked when duplicating the packet
			if sch.quotas[pathID] < currentQuota {
				return pth
			}
		}
	}

	return nil
}

// Lock of s.paths must be held
func (sch *scheduler) selectPath(s *session, hasRetransmission bool, hasStreamRetransmission bool, fromPth *path) *path {
	// XXX Currently round-robin
	// TODO select the right scheduler dynamically

	// DERA: Initial selection excludes the initial Path 0 and deploys new paths.
	pth := sch.selectInitialPath(s, hasRetransmission, hasStreamRetransmission, fromPth)
	if pth != nil {
		return pth
	}

	// Select the scheduling algorithm based on preset
	switch SchedulerAlgorithm {
	case "lowRTT":
		// DERA: lowRTT will also select lowest RTT path for retransmissions, even if that path has no space in its cwnd!
		return sch.selectPathLowLatency(s, hasRetransmission, hasStreamRetransmission, fromPth)
	case "RR":
		return sch.selectPathRoundRobin(s, hasRetransmission, hasStreamRetransmission, fromPth)
	case "oppRedundant":
		// Select any free-to-send path
		return sch.selectFreePath(s, hasRetransmission, hasStreamRetransmission, fromPth)
	case "utilRepair":
		// Select path with the potentially highest bandwidth
		return sch.selectPathHighBW(s, hasRetransmission, hasStreamRetransmission, fromPth)
	default:
		// Error invalid scheduling algorithm
		utils.Debugf("Invalid scheduler algorithm specified!")
		return nil
	}
}

// Lock of s.paths must be free (in case of log print)
func (sch *scheduler) performPacketSending(s *session, windowUpdateFrames []*wire.WindowUpdateFrame, pth *path) (*ackhandler.Packet, bool, error) {
	// add a retransmittable frame
	if pth.sentPacketHandler.ShouldSendRetransmittablePacket() {
		s.packer.QueueControlFrame(&wire.PingFrame{}, pth)
	}
	packet, err := s.packer.PackPacket(pth)
	if err != nil || packet == nil {
		return nil, false, err
	}
	if err = s.sendPackedPacket(packet, pth); err != nil {
		return nil, false, err
	}

	// send every window update twice
	for _, f := range windowUpdateFrames {
		s.packer.QueueControlFrame(f, pth)
	}

	// Packet sent, so update its quota
	sch.quotas[pth.pathID]++

	// Provide some logging if it is the last packet
	/*for _, frame := range packet.frames {
		switch frame := frame.(type) {
		case *wire.StreamFrame:
			if frame.FinBit {
				// Last packet to send on the stream, print stats
				s.pathsLock.RLock()
				utils.Infof("Info for stream %x of %x", frame.StreamID, s.connectionID)
				for pathID, pth := range s.paths {
					if pathID == protocol.InitialPathID && len(s.paths) > 1 {
						continue
					}
					sntPkts, sntRetrans, sntLost, sntBytes := pth.sentPacketHandler.GetStatistics()
					rcvPkts, rcvBytes := pth.receivedPacketHandler.GetStatistics()

					if sch.lastSentBytes == nil {
						sch.lastSentBytes = make(map[protocol.PathID]uint64)
					}

					utils.Infof("Path %x (%v - %v): sent %d (%d B) retrans %d lost %d; rcv %d (%d B) rtt %v\n",
						pathID, pth.conn.LocalAddr(), pth.conn.RemoteAddr(), sntPkts, sntBytes, sntRetrans, sntLost, rcvPkts, rcvBytes, pth.rttStats.SmoothedRTT())
				}
				s.pathsLock.RUnlock()
			}
		default:
		}
	}*/

	pkt := &ackhandler.Packet{
		PacketNumber:    packet.number,
		Frames:          packet.frames,
		Length:          protocol.ByteCount(len(packet.raw)),
		EncryptionLevel: packet.encryptionLevel,
	}

	return pkt, true, nil
}

// Lock of s.paths must be free
func (sch *scheduler) ackRemainingPaths(s *session, totalWindowUpdateFrames []*wire.WindowUpdateFrame) error {
	// Either we run out of data, or CWIN of usable paths are full
	// Send ACKs on paths not yet used, if needed. Either we have no data to send and
	// it will be a pure ACK, or we will have data in it, but the CWIN should then
	// not be an issue.
	s.pathsLock.RLock()
	defer s.pathsLock.RUnlock()
	// get WindowUpdate frames
	// this call triggers the flow controller to increase the flow control windows, if necessary
	windowUpdateFrames := totalWindowUpdateFrames
	if len(windowUpdateFrames) == 0 {
		windowUpdateFrames = s.getWindowUpdateFrames(s.peerBlocked)
	}
	for _, pthTmp := range s.paths {
		ackTmp := pthTmp.GetAckFrame()
		for _, wuf := range windowUpdateFrames {
			s.packer.QueueControlFrame(wuf, pthTmp)
		}
		if ackTmp != nil || len(windowUpdateFrames) > 0 {
			if pthTmp.pathID == protocol.InitialPathID && ackTmp == nil {
				continue
			}
			swf := pthTmp.GetStopWaitingFrame(false)
			if swf != nil {
				s.packer.QueueControlFrame(swf, pthTmp)
			}
			s.packer.QueueControlFrame(ackTmp, pthTmp)
			// XXX (QDC) should we instead call PackPacket to provides WUFs?
			var packet *packedPacket
			var err error
			if ackTmp != nil {
				// Avoid internal error bug
				packet, err = s.packer.PackAckPacket(pthTmp)
			} else {
				packet, err = s.packer.PackPacket(pthTmp)
			}
			if err != nil {
				return err
			}
			err = s.sendPackedPacket(packet, pthTmp)
			if err != nil {
				return err
			}
		}
	}
	s.peerBlocked = false
	return nil
}

func (sch *scheduler) sendPacket(s *session) error {
	var pth *path

	// Update leastUnacked value of paths
	s.pathsLock.RLock()
	for _, pthTmp := range s.paths {
		pthTmp.SetLeastUnacked(pthTmp.sentPacketHandler.GetLeastUnacked())
	}
	s.pathsLock.RUnlock()

	// get WindowUpdate frames
	// this call triggers the flow controller to increase the flow control windows, if necessary
	windowUpdateFrames := s.getWindowUpdateFrames(false)
	for _, wuf := range windowUpdateFrames {
		s.packer.QueueControlFrame(wuf, pth)
	}

	// Repeatedly try sending until we don't have any more data, or run out of the congestion window
	for {
		// We first check for retransmissions
		hasRetransmission, retransmitHandshakePacket, fromPth := sch.getRetransmission(s)
		// XXX There might still be some stream frames to be retransmitted
		hasStreamRetransmission := s.streamFramer.HasFramesForRetransmission()

		// Select the path here
		// DERA: also select possible paths for redundant sendings.
		s.pathsLock.RLock()
		pth = sch.selectPath(s, hasRetransmission, hasStreamRetransmission, fromPth)
		pths := sch.selectRedundantPaths(s, hasRetransmission, hasStreamRetransmission, fromPth)
		s.pathsLock.RUnlock()

		// XXX No more path available, should we have a new QUIC error message?
		if pth == nil {
			windowUpdateFrames := s.getWindowUpdateFrames(false)
			return sch.ackRemainingPaths(s, windowUpdateFrames)
		}

		// If we have an handshake packet retransmission, do it directly
		if hasRetransmission && retransmitHandshakePacket != nil {
			s.packer.QueueControlFrame(pth.sentPacketHandler.GetStopWaitingFrame(true), pth)
			packet, err := s.packer.PackHandshakeRetransmission(retransmitHandshakePacket, pth)
			if err != nil {
				return err
			}
			if err = s.sendPackedPacket(packet, pth); err != nil {
				return err
			}
			continue
		}

		// XXX Some automatic ACK generation should be done someway
		var ack *wire.AckFrame

		ack = pth.GetAckFrame()
		if ack != nil {
			s.packer.QueueControlFrame(ack, pth)
		}
		if ack != nil || hasStreamRetransmission {
			swf := pth.sentPacketHandler.GetStopWaitingFrame(hasStreamRetransmission)
			if swf != nil {
				s.packer.QueueControlFrame(swf, pth)
			}
		}

		// Also add CLOSE_PATH frames, if any
		for cpf := s.streamFramer.PopClosePathFrame(); cpf != nil; cpf = s.streamFramer.PopClosePathFrame() {
			s.packer.QueueControlFrame(cpf, pth)
		}

		// Also add ADD ADDRESS frames, if any
		for aaf := s.streamFramer.PopAddAddressFrame(); aaf != nil; aaf = s.streamFramer.PopAddAddressFrame() {
			s.packer.QueueControlFrame(aaf, pth)
		}

		// Also add PATHS frames, if any
		for pf := s.streamFramer.PopPathsFrame(); pf != nil; pf = s.streamFramer.PopPathsFrame() {
			s.packer.QueueControlFrame(pf, pth)
		}

		pkt, sent, err := sch.performPacketSending(s, windowUpdateFrames, pth)
		if err != nil {
			return err
		}
		windowUpdateFrames = nil
		if !sent {
			// Prevent sending empty packets
			return sch.ackRemainingPaths(s, windowUpdateFrames)
		}

		// Duplicate traffic when it was sent on an unknown performing path
		// FIXME adapt for new paths coming during the connection
		// DERA: redundant schedulers will duplicate packet anyways.
		if pth.rttStats.SmoothedRTT() == 0 && SchedulerAlgorithm != "oppRedundant" {
			currentQuota := sch.quotas[pth.pathID]
			// Was the packet duplicated on all potential paths?
		duplicateLoop:
			for pathID, tmpPth := range s.paths {
				if pathID == protocol.InitialPathID || pathID == pth.pathID {
					continue
				}
				if sch.quotas[pathID] < currentQuota && tmpPth.sentPacketHandler.SendingAllowed() {
					// Duplicate it
					pth.sentPacketHandler.DuplicatePacket(pkt)
					break duplicateLoop
				}
			}
		}

		// Retransmit packets on all valid paths.
		redundantRetransmission := hasRetransmission && hasStreamRetransmission && SchedulerAlgorithm == "utilRepair"

		if SchedulerAlgorithm == "oppRedundant" || redundantRetransmission {
			// Get the frames that should be duplicated
			redundantFrames := pkt.GetCopyFrames()
			if redundantFrames == nil {
				// Prevent duplicating empty packets
				return sch.ackRemainingPaths(s, windowUpdateFrames)
			}

			for _, redPth := range pths {
				if redPth.pathID == protocol.InitialPathID || redPth.pathID == pth.pathID {
					continue
				}
				// Clone duplicable Frames from packet
				encLevel, sealer := s.packer.cryptoSetup.GetSealer()
				publicHeader := s.packer.getPublicHeader(encLevel, redPth)
				raw, err := s.packer.writeAndSealPacket(publicHeader, redundantFrames, sealer, redPth)
				if err != nil {
					continue
				}
				dupPkt := &packedPacket{
					number:          publicHeader.PacketNumber,
					raw:             raw,
					frames:          redundantFrames,
					encryptionLevel: encLevel,
				}
				sch.duplicatedPackets++
				// Add mapping for duplicated packet
				sch.dupPackets[dupID{pth.pathID, pkt.PacketNumber}] = dupID{redPth.pathID, dupPkt.number}
				// Extend mapping to bidirection, if original packet is droppable
				if pkt.IsDupDroppable() {
					sch.dupPackets[dupID{redPth.pathID, dupPkt.number}] = dupID{pth.pathID, pkt.PacketNumber}
				}
				// Send duplicated packet
				err = s.sendPackedPacket(dupPkt, redPth)
				if err != nil {
					continue
				}
				sch.duplicatedStreamBytes += pkt.GetStreamFrameLength()
			}
		}

		// And try pinging on potentially failed paths
		if fromPth != nil && fromPth.potentiallyFailed.Get() {
			err := s.sendPing(fromPth)
			if err != nil {
				return err
			}
		}
	}
}

// Stop already acknowledged packet duplications from beeing send again.
func (sch *scheduler) crossAckHandling(pathID protocol.PathID, packetNumber protocol.PacketNumber) {

	dupKey := dupID{pathID, packetNumber}
	if dupEntry, exists := sch.dupPackets[dupKey]; exists {
		// Try to remove packet from other paths history
		removed := (*sch.pathsRef)[dupEntry.PathID].sentPacketHandler.RemovePacketByNumber(dupEntry.PacketNumber)
		if removed {
			utils.Debugf("Dropped duplicate packet %d on path %d", packetNumber, pathID)
			sch.droppedDuplicatedPackets++
		}
		// Remove bidirectional back mapping (delete does NOP if map does not contain key)
		delete(sch.dupPackets, dupEntry)
	}
	// Remove mapping (delete does NOP if map does not contain key)
	delete(sch.dupPackets, dupKey)
}

// Periodic sending log routine
func (sch *scheduler) LogSendings(s *session, ticker *time.Ticker, stopLog chan struct{}) {

	for {
		select {
		case <-ticker.C:
			// Received logging tick, perform logging routine
			if len(sch.logFiles) < len(s.paths) {
				if sch.logFiles == nil {
					// Create data structures for logging
					sch.logFiles = make(map[protocol.PathID]*os.File)
					sch.lastSentBytes = make(map[protocol.PathID]uint64)
					// Setup the initial logStart time for reference
					sch.logStartTS = time.Now().UnixNano()
					sch.lastLogTS = float64(sch.logStartTS) / 1e6
				}
				// Open log files
				for pathID := range s.paths {
					if _, exists := sch.logFiles[pathID]; !exists {
						filename := "P" + strconv.Itoa(int(pathID)) + "_send.log"
						sch.logFiles[pathID], _ = os.OpenFile(filename, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
					}
				}
			}

			s.pathsLock.RLock()
			// Time measuring
			now := time.Now().UnixNano()
			elapsed := float64(now)/1e6 - sch.lastLogTS
			sch.lastLogTS = float64(now) / 1e6
			// Transform absolute to relative [ms] timestamp string
			timestring := strconv.FormatFloat(float64(now-sch.logStartTS)/1e6, 'f', -1, 64)
			sch.allSntBytes = 0
			for pathID, pth := range s.paths {
				if pathID == protocol.InitialPathID && len(s.paths) > 1 {
					continue
				}
				sntPkts, sntRetrans, sntLost, sntBytes := pth.sentPacketHandler.GetStatistics()
				rcvPkts, rcvBytes := pth.receivedPacketHandler.GetStatistics()

				// sendRate over the last period in KBit/s
				sentDelta := sntBytes - sch.lastSentBytes[pathID]
				sendRate := float64(sentDelta) * 8.0 / elapsed
				// Update lastSentBytes for this path for the next measurement
				sch.lastSentBytes[pathID] = sntBytes

				sch.allSntBytes += sntBytes

				utils.Debugf("Path %x (%v - %v): sent %d (%d B) retrans %d lost %d; rcv %d (%d B) rtt %v\n",
					pathID, pth.conn.LocalAddr(), pth.conn.RemoteAddr(), sntPkts, sntBytes, sntRetrans, sntLost, rcvPkts, rcvBytes, pth.rttStats.SmoothedRTT())
				utils.Debugf("Elapsed %f ms, Sent Bytes %d, Send rate %f KBit/s", elapsed, sentDelta, sendRate)

				if LogPayload {
					logLine := timestring + ";" + strconv.FormatFloat(sendRate, 'g', -1, 64) + "\n"
					sch.logFiles[pathID].WriteString(logLine)
				}
			}
			s.pathsLock.RUnlock()
			s.scheduler.logRedundantStats(s)
		case <-stopLog:
			// Stop logging
			ticker.Stop()
			return
		}
	}
}

// Log statistics on duplicated Packets to file, when a redundant scheduler is used
func (sch *scheduler) logRedundantStats(s *session) {

	if SchedulerAlgorithm == "oppRedundant" || SchedulerAlgorithm == "utilRepair" {
		filename := "Server_scheduler_stats.json"
		os.Remove(filename)
		logStatsFile, _ := os.OpenFile(filename, os.O_CREATE|os.O_WRONLY, 0644)

		dupQuota := 0.0
		if sch.allSntBytes != 0 {
			dupQuota = float64(sch.duplicatedStreamBytes) / float64(sch.allSntBytes) * 100.0
		}
		utils.Debugf("Duplicated Stream Bytes %d (%f %%)", sch.duplicatedStreamBytes, dupQuota)

		dropQuota := 0.0
		if sch.duplicatedPackets != 0 {
			dropQuota = float64(sch.droppedDuplicatedPackets) / float64(sch.duplicatedPackets) * 100.0
		}
		utils.Debugf("Total redundant droppings %d/%d (%f %%)", sch.droppedDuplicatedPackets, sch.duplicatedPackets, dropQuota)

		logStatsFile.WriteString(
			"{ \"totalSentPackets\" : " + strconv.FormatUint(s.allSntPackets, 10) +
				", \"duplicatedPackets\" : " + strconv.FormatUint(sch.duplicatedPackets, 10) +
				", \"duplicatedDroppedPackets\" : " + strconv.FormatUint(sch.droppedDuplicatedPackets, 10) +
				", \"duplicatedPacketDropRate\" : " + strconv.FormatFloat(dropQuota, 'g', -1, 64) +
				", \"totalStreamBytes\" : " + strconv.FormatUint(sch.allSntBytes, 10) +
				", \"duplicatedStreamBytes\" : " + strconv.FormatUint(sch.duplicatedStreamBytes, 10) +
				", \"duplicateStreamRate\" : " + strconv.FormatFloat(dupQuota, 'g', -1, 64) +
				"}")

		logStatsFile.Close()
	}
}
