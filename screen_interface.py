import threading
from rich import print as pr
import sys
import socket
import enum
import os

class TypeMessage(enum.Enum):
    PRINT="[print]"
    INPUT="[input]"
    BASE ="[basic]"
    CLOSE="[close]"

class Screen:
    def __init__(self, prt: int) -> None:
        self.port = prt
        self.accept_input = False


    def connect(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        def getin():
            resp = input(">>> ")
            client.send(resp.encode())
        try:
            client.connect(("127.0.0.1", self.port))
            client.send(str(os.getpid()).encode())
            while 1:
                res = client.recv(1024).decode().rstrip("\x00")
                typ, msg = res[:len(TypeMessage.BASE.value)], res[len(TypeMessage.BASE.value):]
                if len(msg)>0 and msg != "ping":
                    pr(msg)
                if typ == TypeMessage.CLOSE.value:
                    client.close()
                    sys.exit(0)
                elif typ == TypeMessage.INPUT.value:
                    threading.Thread(target=getin).start()
            

        except:
            sys.exit(-1)

if len(sys.argv) > 1:
    try:
        port = int(sys.argv[1])
        scrn = Screen(port)
        scrn.connect()
    except:
        sys.exit(-1)