import zenoh, time, numpy as np
from teleai_zenoh_wrapper.infoclasses import TimestampedStrPacket
from teleai_zenoh_wrapper.pubsub import ZenohConfFactory

# Publisher
session = zenoh.open(zenoh.Config.from_json5(
    ZenohConfFactory.create_default().to_str()
))
def callback(sample):
    pkt = TimestampedStrPacket.from_bytes(bytes(sample.payload))
    print(pkt.timestamp_ns, pkt.text)

sub = session.declare_subscriber("my/topic", callback)
time.sleep(1)


pub = session.declare_publisher("my/topic")

pkt = TimestampedStrPacket(timestamp_ns=np.uint64(time.time_ns()), text="hello zenoh 02120500541508105105454185050")
pub.put(pkt.to_bytes())
