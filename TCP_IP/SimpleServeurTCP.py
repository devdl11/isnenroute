import socket

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

server.bind(("", 1234))
server.listen(1)

print("IP : PORT", server.getsockname())

online = True
while online:
    cli, adrs = server.accept()
    try:
        message = cli.recv(1024).decode()
        if message == "closeserv":
            online = False
        else:
            print("Message : ", message)
        cli.send(b"Hello World!")
    except:
        cli.close()
    cli.close()

print("Serveur Fermé!")