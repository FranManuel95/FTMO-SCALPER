import zmq
from datetime import datetime, timedelta

ctx  = zmq.Context()
push = ctx.socket(zmq.PUSH)
pull = ctx.socket(zmq.PULL)
push.connect("tcp://localhost:32768")
pull.connect("tcp://localhost:32769")
pull.setsockopt(zmq.RCVTIMEO, 3000)

end   = datetime.utcnow()
start = end - timedelta(hours=48)

for tf in range(30, 80):
    cmd = f"HIST;EURUSD;{tf};{start.strftime('%Y.%m.%d %H:%M')};{end.strftime('%Y.%m.%d %H:%M')}"
    try:
        push.send_string(cmd)
        resp = pull.recv_string()
        if resp and "'time'" in resp:
            count  = resp.count("'time'")
            symbol = resp.split("'_symbol': '")[1].split("'")[0]
            print(f"TF={tf} -> {symbol} ({count} velas)")
    except:
        pass

print("Test completado")
ctx.term()