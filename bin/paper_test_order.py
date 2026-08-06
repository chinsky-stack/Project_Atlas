import sys, json
sys.path.insert(0, "src")
import yaml

# Load merged config (config.yaml + gitignored config.local.yaml with paper keys)
cfg = yaml.safe_load(open("config.yaml"))
loc = yaml.safe_load(open("config.local.yaml"))
def merge(b, o):
    for k, v in o.items():
        if isinstance(v, dict) and isinstance(b.get(k), dict):
            merge(b[k], v)
        else:
            b[k] = v
merge(cfg, loc)

from broker import get_broker

class MD:
    def get_price(self, t): return 0.0
class PT:
    pass

b = get_broker(cfg, MD(), PT())
print("Broker:", b.label, "| live:", getattr(b, "is_live", None))

# Small high-conviction PAPER order: long a liquid name, sized by Risk Office.
ticker = "AAPL"
direction = "Long"
conviction = 8
stop = 300.0  # hard stop well below market (~324) -> Soros cut
res = b.submit_order(ticker, direction, conviction, stop)
print("ORDER RESULT:")
print("  ok:", res.ok)
print("  msg:", res.message)
if res.position:
    print("  position:", json.dumps(res.position))
