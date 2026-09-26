# RF Traffic Monitor design

RF Traffic Monitor is a portable, local-first Windows application for receiving
and displaying ADS-B, AIS, ACARS, VDL2, HFDL, RS41, and compatible Wi-Fi Remote
ID traffic. It uses a configurable station location and generates offline map
data around the location selected during setup.

One SDR can tune only a limited continuous frequency window at a time. The
application therefore gives ADS-B priority and cycles the receiver between
selected modes. Messages transmitted while the receiver is tuned elsewhere are
not recovered later. Nearby channels for the same protocol may be decoded
together when they fit within the supported bandwidth.

The controller gives one decoder exclusive ownership of the SDR, waits for it
to exit before starting the next decoder, and records position age independently
from metadata. Messages without a confirmed current position remain in the
message list instead of creating arbitrary map targets.

The HTTP dashboard binds to loopback only. Runtime assets and maps are local,
and the application does not configure feeder services. Wi-Fi Remote ID uses a
separate adapter and can run in parallel with the SDR receiver.

Map coverage describes the displayed area and does not guarantee reception
range. Hardware, antenna, terrain, frequency, and propagation determine actual
reception.
