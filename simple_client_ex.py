import socket
import threading

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

client.connect(("192.168.100.210", 7823))

def recveiver():
    while 1:
        buf= client.recv(1024).decode().rstrip("\x00")
        if len(buf) > 0 and buf != "ping":
            print(buf)

threading.Thread(target=recveiver).start()

while 1:
    rep = input()
    if rep == "quit":
        client.close
        break
    else:
        client.send(rep.encode())
        