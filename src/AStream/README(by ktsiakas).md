AStream :
--------------------------------------
--------------------------------------
forked by [pari685](https://github.com/pari685/AStream) and modified



::changes in read_mpd
--------------------------------------

The astream-client was able to read mpd files with the following format:

```xml
<myxml>
<?xml version="1.0" encoding="UTF-8"?>
<!-- MPD file Generated with GPAC version 0.5.1-DEV-rev5379  on 2014-09-10T13:30:18Z-->
<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" minBufferTime="PT1.500000S" type="static" mediaPresentationDuration="PT0H9M56.46S" profiles="urn:mpeg:dash:profile:isoff-live:2011">
    <Period duration="PT0H9M56.46S">
        <AdaptationSet mimeType="video/mp4" segmentAlignment="true" group="1" maxWidth="480" maxHeight="360" maxFrameRate="24" par="4:3">
            <Representation id="320x240 45.0kbps" mimeType="video/mp4" codecs="avc1.42c00d" width="320"  height="240" frameRate="24" sar="1:1" startWithSAP="1"  bandwidth="45226" >
                <SegmentTemplate timescale="96" media="media/BigBuckBunny/4sec/bunny_$Bandwidth$bps/BigBuckBunny_4s$Number$%d.m4s" startNumber="1" duration="384" initialization="media/BigBuckBunny/4sec/bunny_$Bandwidth$bps/BigBuckBunny_4s_init.mp4" />
                <SegmentSize id="BigBuckBunny_4s1.m4s" size="168.0" scale="Kbits"/>
                <SegmentSize id="BigBuckBunny_4s2.m4s" size="184.0" scale="Kbits"/>
            </Representation>
        </AdaptationSet>
    </Period>
</MPD>
</myxml>
```

but in [itec](http://www-itec.uni-klu.ac.at/ftp/datasets/mmsys12/)
there were many MPDs with different format than this one, that we needed to use for our experiment.
So, we added and changed a few lines in the client's read_mpd.py and now it is able to read MPDs with the following format too.
```xml
<myxml>
<?xml version="1.0" encoding="UTF-8"?>
<MPD xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xmlns="urn:mpeg:DASH:schema:MPD:2011"
xsi:schemaLocation="urn:mpeg:DASH:schema:MPD:2011"
profiles="urn:mpeg:dash:profile:isoff-main:2011"
type="static"
mediaPresentationDuration="PT0H9M56.46S"
minBufferTime="PT2.0S">
    <BaseURL>http://127.0.0.1/media/</BaseURL>
    <Period start="PT0S">
        <AdaptationSet bitstreamSwitching="true">
            <Representation id="0" codecs="avc1.4d401f" mimeType="video/mp4" width="320" height="240" startWithSAP="1" bandwidth="45652">
                <SegmentBase>
                <Initialization sourceURL="bunny_2s_50kbit/bunny_50kbit_dash.mp4"/>
                </SegmentBase>
                <SegmentList duration="2">
                    <SegmentURL media="bunny_2s_50kbit/bunny_2s1.m4s"/>
                    <SegmentURL media="bunny_2s_50kbit/bunny_2s2.m4s"/>
                </SegmentList>
            </Representation>
        </AdaptationSet>
    </Period>
</MPD>
</myxml>
```

for more view [client directory](https://github.com/ktsiakas/AStream/tree/master/dist/client) and commit [90ab5d3](https://github.com/ktsiakas/AStream/commit/90ab5d387ece879ee6e7d1de69ea6fe4052eee03)
---------------

