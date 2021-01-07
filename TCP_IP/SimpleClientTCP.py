import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

online = True
client.connect(("127.0.0.1", 1234))
client.send(b"Coucou")

while online:
    try:
        message = client.recv(1024).decode()
        print("Serveur: ", message)
        res = input(">>> ")
        if res == "quit":
            online = False
            continue
        client.send(res.encode())
    except socket.error:
        print("Erreur connexion ! ")
        online= False
    except:continue

client.close()
print("Connexion Fermé!")