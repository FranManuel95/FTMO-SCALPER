import zmq
import time
from datetime import datetime, timedelta

ctx  = zmq.Context()
push = ctx.socket(zmq.PUSH)
pull = ctx.socket(zmq.PULL)
push.connect("tcp://localhost:32768")
pull.connect("tcp://localhost:32769")
pull.setsockopt(zmq.RCVTIMEO, 5000)
time.sleep(1)

end   = datetime.utcnow()
start = end - timedelta(hours=3)
s = start.strftime('%Y.%m.%d %H:%M')
e = end.strftime('%Y.%m.%d %H:%M')

# Probar formatos del comando HIST
comandos = [
    f"HIST;EURUSD;1;{s};{e}",
    f"HIST;EURUSD;5;{s};{e}",
    f"HIST;EURUSD;9;{s};{e}",
    f"HIST;EURUSD;M5;{s};{e}",
    f"HIST;EURUSD;1;{s};{e};0;0;0;0;0;0",
]

for cmd in comandos:
    print(f"\nEnviando: {cmd[:60]}")
    push.send_string(cmd)
    try:
        resp = pull.recv_string()
        if resp and "'time'" in resp:
            count = resp.count("'time'")
            print(f"OK - {count} velas")
        else:
            print(f"Respuesta: {resp[:100] if resp else 'VACIA'}")
    except Exception as e:
        print(f"Timeout: {e}")
    time.sleep(0.3)

ctx.term()