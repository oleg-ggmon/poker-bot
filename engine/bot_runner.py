"""Child-process harness that hosts one bot.

Usage: python bot_runner.py path/to/bot.py

Speaks JSON lines with the dealer: reads requests on stdin, writes replies
on the original stdout. Anything the bot prints goes to stderr so it can't
corrupt the protocol.
"""
import importlib.util
import json
import os
import sys
import traceback


def normalise(result):
    if isinstance(result, dict):
        return {"action": result.get("action"), "amount": result.get("amount")}
    if isinstance(result, (tuple, list)):
        return {"action": result[0] if result else None,
                "amount": result[1] if len(result) > 1 else None}
    if isinstance(result, str):
        return {"action": result, "amount": None}
    return {"action": None, "amount": None}


def main():
    proto = os.fdopen(os.dup(1), "w", buffering=1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr

    def send(obj):
        proto.write(json.dumps(obj) + "\n")
        proto.flush()

    path = os.path.abspath(sys.argv[1])
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec = importlib.util.spec_from_file_location("bot", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        Agent = getattr(module, "Agent")
    except Exception:
        send({"type": "load_error", "error": traceback.format_exc(limit=6)})
        return
    send({"type": "loaded"})

    agent = None
    for line in sys.stdin:
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        kind = msg.get("type")
        if kind == "new_table":
            try:
                agent = Agent()
                if hasattr(agent, "on_table_start"):
                    agent.on_table_start(msg.get("info", {}))
                send({"id": msg["id"], "type": "ready"})
            except Exception:
                agent = None
                send({"id": msg["id"], "type": "error", "error": traceback.format_exc(limit=6)})
        elif kind == "act":
            try:
                reply = normalise(agent.act(msg["state"]))
                reply.update(id=msg["id"], type="action")
                send(reply)
            except Exception:
                send({"id": msg["id"], "type": "error", "error": traceback.format_exc(limit=6)})
        elif kind == "hand_end":
            if agent is not None and hasattr(agent, "on_hand_end"):
                try:
                    agent.on_hand_end(msg["summary"])
                except Exception:
                    pass
        elif kind == "quit":
            break


if __name__ == "__main__":
    main()
