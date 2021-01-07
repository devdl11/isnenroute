import datetime
from colorama.initialise import init
from rich.console import Console
from rich.table import Table
import json
import os
import enum
import pynput
import uuid
import threading
import time
import socket
import subprocess
from contextlib import closing
import sys
import psutil
import queue
import typing

# --- Core def --- 
FIREWALL_MODULE = None
SERVER_MODULE = None
CONFIG = {}
ERROR = uuid.uuid4()
DEFAULT_ENCODING = "UTF-8"

PORT_USED = [
    7823
]

class TYPES(enum.Enum):
    FIREWALL = 0
    ROOM = 1
    MODULE = 2

def get_freeport() -> int:
    freeport = None
    while freeport is None or freeport in PORT_USED: 
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(("127.0.0.1", 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            freeport = s.getsockname()[1]
    return freeport

class ScreenServer:
    class TypeMessage(enum.Enum):
        PRINT="[print]"
        INPUT="[input]"
        BASE ="[basic]"
        CLOSE="[close]"

    def __init__(self) -> None:
        self.screen_proc = subprocess.Popen
        self.is_connect = False
        self.processing = psutil.Process
        self.closing = False
        self.PID = None
        self.queue_in = queue.Queue()
        self.queue_out = queue.Queue()
        self.history = list()
        self.isrestarting = False

    def worker(self, port:int):
        serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serv.bind(("127.0.0.1", port))

        is_running = True
        screen = None

        def accept_instance():
            nonlocal screen
            serv.listen()
            serv.settimeout(10)
            while is_running:
                try:
                    if screen is None:
                        screen, adrs = serv.accept()
                        self.PID = int(screen.recv(1024))
                except:
                    continue

        threading.Thread(target=accept_instance).start()
        def getin(packet):
            screen.send(packet)
            recv = screen.recv(1024).decode()
            self.history.append(ScreenServer.TypeMessage.PRINT.value + msg)
            self.history.append(ScreenServer.TypeMessage.PRINT.value + ">>> " +recv)
            self.queue_out.put(recv)
        while is_running:
            if screen is not None:
                try:
                    if self.isrestarting:
                        for i in self.history:
                            packet = i.encode()
                            packetF = bytearray(1024)
                            packetF[0:len(packet)]=packet
                            screen.send(packet)
                        self.isrestarting = False
                    content = self.queue_in.get(block=True, timeout=None)
                    if content == "screenclosed":
                        self.isrestarting = True
                        screen.close()
                        screen = None
                        continue
                    typ, msg = content[:len(ScreenServer.TypeMessage.BASE.value)], content[len(ScreenServer.TypeMessage.BASE.value):]
                    if typ == ScreenServer.TypeMessage.PRINT.value:
                        packet = str(ScreenServer.TypeMessage.PRINT.value).encode() + str(msg).encode()
                        packetF = bytearray(1024)
                        packetF[0:len(packet)]=packet
                        self.history.append(content)
                        screen.send(packetF)
                    elif typ == ScreenServer.TypeMessage.INPUT.value:
                        packet = str(ScreenServer.TypeMessage.INPUT.value).encode() + str(msg).encode()
                        packetF = bytearray(1024)
                        packetF[0:len(packet)]=packet
                        threading.Thread(target=getin, args=[packet]).start()
                        
                    elif typ == ScreenServer.TypeMessage.CLOSE.value:
                        screen.send(b"close")
                        is_running = False
                        screen = screen.close()
                except:
                    try:
                        packet = b"ping"
                        packetF = bytearray(1024)
                        packetF[0:len(packet)]=packet
                        screen.send(packetF)
                    except:
                        screen.close()
                        screen = None
                        self.PID = 0
                    continue
        
    def print(self, msg:str):
        self.queue_in.put(ScreenServer.TypeMessage.PRINT.value + msg)

    def input(self, msg:str) -> str:
        self.queue_in.put(ScreenServer.TypeMessage.INPUT.value + msg)
        return self.queue_out.get()

    def run(self):
        freeport = get_freeport()
        
        self.processing = threading.Thread(target=self.worker, args=[freeport])
        self.processing.start()
        self.screen_proc = subprocess.Popen(["start", sys.executable, "screen_interface.py", str(freeport)], shell=True)
        
        while self.PID is None:pass

        self.screen_proc = psutil.Process(self.PID)

        def stay_alive():
            while not self.closing:
                try:
                    if not self.screen_proc.is_running():
                        self.PID = None
                        self.queue_in.put("screenclosed")
                        subprocess.Popen(["start", sys.executable, "screen_interface.py", str(freeport)], shell=True)
                        while self.PID is None:pass
                        self.screen_proc = psutil.Process(self.PID)
                except:pass
                
        threading.Thread(target=stay_alive, daemon=True).start()

    def close(self):
        self.queue_in.put(ScreenServer.TypeMessage.CLOSE.value)
        self.is_connect = False
        self.queue_in.task_done()
        self.queue_out.task_done()
        self.closing = True
        time.sleep(0.5)
        self.screen_proc.kill()

class BasicClient:
    def __init__(self, sock: socket.socket, adrs) -> None:
        self.user_socket = sock
        self.adrs = adrs
        self.is_valid = True

    def send(self, content: typing.Union[str, bytes, bytearray]) -> bool:
        if not self.is_valid:
            return False
        try:
            if type(content) is str:
                content = content.encode(DEFAULT_ENCODING)
                self.user_socket.send(content)
                return True
            else:
                self.user_socket.send(content)
                return True
        except socket.error:
            self.is_valid = False
            return False
        except:
            return False

    def recv(self, bufsize:int, typ=typing.Union[bytes, str]) -> typing.Union[uuid.UUID, bytes, str]:
        if not self.is_valid:
            return ERROR
        try:
            result = self.user_socket.recv(bufsize)
            if type(typ) == str:
                result = result.decode(DEFAULT_ENCODING)
            return result
        except socket.error:
            self.is_valid = False
            return ERROR
        except:
            return ERROR

    def ping(self):
        if not self.is_valid:
            return
        try:
            self.user_socket.send(b"ping")
        except:
            self.is_valid = False

    def close(self):
        self.is_valid = False
        self.user_socket.close()

class FirewallClient(BasicClient):
    def async_recv(self):
        while self.is_valid:
            if self.socket_forward.fileno() == -1:
                self.firewall.disconnect_socket(self)
                continue
            if self.is_valid:
                buf = self.recv(1024, bytes())
                if buf != ERROR:
                    try:
                        buf.decode(DEFAULT_ENCODING)
                        # self.firewall.screen.print(buf.decode(DEFAULT_ENCODING))
                    except:
                        self.firewall.log("Corrupt packet received from " + str(self.adrs[0]))
                        self.firewall.screen.print("[red] Corrupt packet received from " + str(self.adrs[0]))
                        continue
                    if self.is_valid:
                        try:
                            packetF = bytearray(1024)
                            packetF[:len(buf)] = buf
                            self.socket_forward.send(packetF)
                        except:
                            self.firewall.disconnect_socket(self)

    def async_checking(self):
        while self.is_valid:
            time.sleep(2)
            self.ping()
            self.ping2()
            if self.socket_forward.fileno() == -1:
                break
        self.firewall.disconnect_socket(self)
    
    def ping2(self):
        if not self.is_valid:
            return
        try:
            self.socket_forward.send(b"ping")
        except:
            self.is_valid = False

    def async_send(self):
        while self.is_valid:
            try:
                if self.is_valid:
                    buf = self.socket_forward.recv(1024)
                    packetF = bytearray(1024)
                    packetF[:len(buf)] = buf
                    self.send(packetF)
            except:continue

    def __init__(self, sock: socket.socket, adrs, firewall) -> None:
        super().__init__(sock, adrs)
        self.firewall = firewall
        self.socket_forward = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket_forward.connect(("127.0.0.1", self.firewall.port_to_forward))
        except:
            self.firewall.log("Error: TCPServer offline! Closing tcp client " + str(adrs[0]))
            self.close()
            return
        packet = str(adrs[0]).encode(DEFAULT_ENCODING)
        packetF = bytearray(1024)
        packetF[:len(packet)] = packet
        self.socket_forward.send(packetF)
        threading.Thread(target=self.async_checking).start()
        threading.Thread(target=self.async_recv).start()
        threading.Thread(target=self.async_send).start()

    def close(self):
        self.is_valid = False
        self.socket_forward.close()
        return super().close()


class BasicFirewall:
    class PARAMETERS(enum.Enum):
        BLOCK_LIST = "blocklist"
        ALLOW_LIST = "allowlist"
        ALLOW_LIST_ONLY = "allowListOnly"
        ACTIVATED = "status"

    NAME = "Firewall"
    VERSION = "0.1"
    DESC = "A simple firewall"
    CONFIG_FILE = "./simple_firewall.json"
    LOG_FILE = "./simple_firewall_logs.txt"
    INPUT_PORT = 7823
    SAVE_DELAY = 5

    def log(self, msg:str):
        with open(self.LOG_FILE, "a") as file:
            now = datetime.datetime.now()
            file.write(f"{now.day}/{now.month}/{now.year} at {now.hour}:{now.minute}:{now.second} --> {msg} \n")

    def _save_config(self):
        self.log("Saving config...")
        content = {}
        content[self.PARAMETERS.ACTIVATED.value] = self.activated
        content[self.PARAMETERS.ALLOW_LIST.value] = self.allow_list
        content[self.PARAMETERS.ALLOW_LIST_ONLY.value] = self.allow_list_only
        content[self.PARAMETERS.BLOCK_LIST.value] = self.block_list
        parsed = json.dumps(content)
        with open(self.CONFIG_FILE,"w") as file:
            file.write(parsed)
        self.log("Saved at " + self.CONFIG_FILE + "!")

    def _auto_config_save(self):
        while self.online:
            time.sleep(self.SAVE_DELAY)
            self._save_config()

    def __init__(self, port: int) -> None:
        self.screen = ScreenServer()
        self.screen.run()

        self.block_list = []
        self.allow_list = []
        self.allow_list_only = False
        self.activated = True
        self.port_to_forward = port
        self.online = True

        self.firewall_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.all_sockets = list()

        self.screen.print("[red on black]#### Application: " + self.NAME + " V. "+ self.VERSION + " ###")
        self.screen.print("[red]-- Initialisation --")

        if not os.path.isfile(self.LOG_FILE):
            with open(self.LOG_FILE, "w") as file:
                file.close()

        self.log("Initialisation du FireWall " + self.NAME + " V. "+ self.VERSION)
        self.log("Vérification de la présence du fichier config " + self.CONFIG_FILE)

        if not os.path.isfile(self.CONFIG_FILE):
            self.log("-- Fichier absent! Création du fichier.")
            with open(self.CONFIG_FILE, "w") as file:
                file.close()
            self.log("-- Fichier créé")
        
        self.log("Lecture du fichier config")

        with open(self.CONFIG_FILE, "r") as file:
            content = file.read()
            if len(content) > 0:
                self.log("Présence de contenu. Tentative de parsing JSON")
                @no_exception
                def work(cont):
                    return json.loads(cont)
                result = work(content)
                if result != ERROR:
                    self.log("Parsing Réussi! Chargement des paramètres")
                    self.block_list = result[self.PARAMETERS.BLOCK_LIST.value]
                    self.allow_list = result[self.PARAMETERS.ALLOW_LIST.value]
                    self.allow_list_only = result[self.PARAMETERS.ALLOW_LIST_ONLY.value]
                    self.activated = result[self.PARAMETERS.ACTIVATED.value]
                    self.log("Chargement des paramètres réussi!")
                else:
                    self.log("Contenu Invalide! Utilisation des paramètres par défaut!")
        
        self.log(f"Paramètres utilisés: \n Taille de la BL: {str(len(self.block_list))}\n Taille de la AL: {str(len(self.allow_list))}\n Uniq. AL: {'Oui' if self.allow_list_only else 'Non'}\n Statut: {'Activé' if self.activated else 'Désactivé'}")
        self.log(f"Port d'entrée: {self.INPUT_PORT}  |  Redirection vers: {self.port_to_forward}")
        self.log("Lancement du processus de sauvegarde automatique")
        threading.Thread(target=self._auto_config_save).start()
        self.log("En attente du serveur...")

        self.screen.print("[red]-- End Initialisation --\n -> Waiting for server...")

    def filter(self, sock, adrs):
        if self.activated:
            if self.allow_list_only and not adrs[0] in self.allow_list:
                self.log("Client " + str(adrs[0]) + " is not in allow list! Connection closed")
                self.screen.print("[italic white] Client " + str(adrs[0]) + " is not in allow list! Connection closed")
                sock.close()
                return
            elif adrs[0] in self.block_list:
                self.log("Client " + str(adrs[0]) + " is in block list! Connection closed")
                self.screen.print("[italic white] Client " + str(adrs[0]) + " is in block list! Connection closed")
                sock.close()
                return
        self.log("Client " + str(adrs[0]) + " accepted! Forwarding to the server")
        self.screen.print("[italic white] Client " + str(adrs[0]) + " accepted! Forwarding to the server")
        firw_cli = FirewallClient(sock, adrs, self)
        self.all_sockets.append(firw_cli)
        

    def start_service(self):
        def worker():
            self.screen.print("[red]Firewall service started! PORT: " +str(self.INPUT_PORT))
            self.firewall_socket.bind(("0.0.0.0", self.INPUT_PORT))
            self.firewall_socket.listen()
            while self.online:
                sock, adrs = self.firewall_socket.accept()
                threading.Thread(target=self.filter, args=[sock, adrs]).start()
        threading.Thread(target=worker).start()

    def disconnect_socket(self, cli: FirewallClient):
        if cli in self.all_sockets:
            self.all_sockets.remove(cli)
        cli.close()
        self.log("Client " + str(cli.adrs[0]) + " disconnected!")
        self.screen.print("[white] Client " + str(cli.adrs[0]) + " disconnected!")
        

    def stop(self):
        self.log("Stopping firewall...")
        self.screen.print("[red] Stopping Firewall")
        self.online = False
        for i in self.all_sockets:
            self.disconnect_socket(i)
        self.firewall_socket.close()
        self.screen.input("[red] Firewall Stopped correctly!")
        self.screen.close()

    def add_to_blocklist(self, adrs: str):
        if not adrs in self.block_list:
            self.log(f"{adrs} added to blocklist!")
            self.block_list.append(adrs)
        
    def remove_from_blocklist(self, adrs: str):
        if adrs in self.block_list:
            self.log(f"{adrs} removed from blocklist!")
            self.block_list.remove(adrs)

    def add_to_allowlist(self, adrs: str):
        if not adrs in self.allow_list:
            self.log(f"{adrs} added to allowlist!")
            self.allow_list.append(adrs)

    def remove_from_allowlist(self, adrs: str):
        if adrs in self.allow_list:
            self.log(f"{adrs} added to allowlist!")
            self.allow_list.remove(adrs)

    def set_firewall_statut(self, stat: bool):
        self.activated = stat
        self.log("Firewall " + "deactivated" if stat is False else "activated" + "!")

    def set_allowlist_only(self, allow: bool):
        self.allow_list_only = allow
        self.log("Allow list only " + "deactivated" if allow is False else "activated" + "!")
    
main_console = Console(width=50)


class BasicTcpChannel:
    NAME = "BasicChannel"

    def __init__(self, limit_members=0) -> None:
        self.clients = list()
        self.limit = limit_members
        self.has_limit = limit_members == 0
        self.message_history = list()
        self.message_type = str()

    def register(self, client: BasicClient) -> bool:
        if not client in self.clients and ((len(self.clients) < self.limit and self.has_limit) or True):
            client.send("You joined the " + self.NAME + " channel!" + "\nMembers online: " + str(len(self.clients)))
            for i in self.clients:
                i.send("User " + str(i.adrs[0]) + " has joined the channel!")
            self.clients.append(client)
            for msg in self.message_history:
                client.send(msg)
            return True
        return False
    
    def remove(self, client: BasicClient):
        if client in self.clients:
            client.send("You left the channel!")
            self.clients.remove(client)
            for i in self.clients:
                i.send("User " + str(i.adrs[0]) + " has left the channel!")
    
    def send(self, client, msg:str):
        if client in self.clients:
            content = str(client.adrs[0]) + " : " + msg
            self.message_history.append(content)
            for i in self.clients:
                if i != client:
                    i.send(content)

class WildServerChannel(BasicTcpChannel):
    NAME = "Wild Channel"

class SelfAloneChannel(BasicTcpChannel):
    NAME = "Alone Channel"

    def __init__(self) -> None:
        super().__init__(limit_members=1)

class ServerClientChannel(BasicTcpChannel):
    NAME = "ServerClient"

    def async_getinput_from_screen(self):
        while self.online:
            res = self.screen.input()
            self.send(None, res)
        self.callback()

    def __init__(self, screen: ScreenServer, callback:typing.Callable) -> None:
        super().__init__(limit_members=1)
        self.screen = screen
        self.online = True
        self.callback = callback
        threading.Thread(target=self.async_getinput_from_screen).start()
        

    def register(self, client: BasicClient) -> bool:
        if len(self.clients) == 0 and self.online:
            client.send("You joined a private channel with server!")
            self.screen.print("[bright_blue] User " + str(client.adrs[0]) + " has joined the channel!")
            self.clients.append(client)
            for msg in self.message_history:
                client.send(msg)
            return True
        return False

    def remove(self, client: BasicClient):
        if client in self.clients and self.online:
            client.send("You left the channel!")
            self.clients.remove(client)
            self.online = False
            
    def send(self, client, msg:str):
        if not self.online:
            return
        if client != None and client in self.clients:
            content = str(client.adrs[0]) + " : " + msg
            self.message_history.append(content)
            self.screen.print("[green3]" + content)
        elif client is None:
            content = "server : " + msg
            self.message_history.append(content)
            self.clients[0].send(content)

class ServerClient(BasicClient):
    def async_recv(self):
        while self.is_valid:
            if self.is_valid:
                buf = self.recv(1024, self.channel.message_type)
                if buf != ERROR:
                    if buf == b"ping":
                        continue
                    self.channel.send(self, buf)
                    if type(self.channel.message_type) is str:
                        content = self.channel.NAME + " : " + buf
                        self.message_history.append(content)

    def async_checking(self):
        while self.is_valid:
            time.sleep(2)
            self.ping()
        
        self.server.disconnect_client(self)

    def disconnect(self):
        self.channel.remove(self)
        self.close()

    def __init__(self, sock: socket.socket, adrs, channel: BasicTcpChannel, server) -> None:
        super().__init__(sock, adrs)
        self.channel = channel
        self.server = server
        self.message_history = list()
        threading.Thread(target=self.async_recv).start()
        threading.Thread(target=self.async_checking).start()

    def change_channel(self, channel: BasicTcpChannel):
        self.channel.remove(self)
        self.channel = channel
        res = channel.register(self)
        if not res:
            self.channel = SelfAloneChannel()
            self.channel.register(self)

    def disconnect_from_channel(self):
        self.channel.remove(self)
        self.channel = SelfAloneChannel()
        self.channel.register(self)

class BasicTcpServer:
    NAME = "TCPServer"
    VERSION = "0.1"
    DESC = "A simple tcp server"
    CONFIG_FILE = "./simple_tcpserver.json"
    LOG_FILE = "./simple_tcpserver_logs.txt"
    SAVE_DELAY = 5

    def log(self, msg:str):
        log(msg)
        with open(self.LOG_FILE, "a") as file:
            now = datetime.datetime.now()
            file.write(f"{now.day}/{now.month}/{now.year} at {now.hour}:{now.minute}:{now.second} --> {msg} \n")

    def __init__(self, port:int, firewall:BasicFirewall) -> None:
        self.port = port
        self.firewall = firewall
        self.all_clients = list()
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.running = True
        self.default_channel = WildServerChannel()
        self.all_channels = list()

        self.on_join_event = None
        self.on_leave_event = None

    def start(self):
        def worker():
            self.server_socket.bind(("127.0.0.1", self.port))
            self.server_socket.listen(0)
            while self.running:
                sock, adrs = self.server_socket.accept()
                real_adrs = sock.recv(1024).decode(DEFAULT_ENCODING).rstrip("\x00")
                new_cli = ServerClient(sock, [real_adrs, adrs[1]], self.default_channel, self)
                self.log("Client logged : " + str(real_adrs) + " --> moved to " + self.default_channel.NAME)
                self.default_channel.register(new_cli)
                self.all_clients.append(new_cli)
                if callable(self.on_join_event):
                    self.on_join_event()
        self.firewall.start_service()
        threading.Thread(target=worker).start()

    def disconnect_client(self, client: ServerClient):
        client.disconnect()
        if client in self.all_clients:
            self.all_clients.remove(client)
            self.log("Client " + str(client.adrs[0]) + " disconnected!")
            if callable(self.on_leave_event):
                self.on_leave_event()

    def stop(self):
        self.log("Stopping TCP server...")
        log("Stopping TCP Server...")
        self.firewall.stop()
        self.running = False
        for i in self.all_clients:
            self.disconnect_client(i)
        self.server_socket.close()
        log("TCPServer stopped correctly ! ")

    def on_join_callback(self, func: typing.Callable):
        self.on_join_event = func

    def on_leave_callback(self, func: typing.Callable):
        self.on_leave_event = func

    def ban_client(self, cli:ServerClient):
        if cli in self.all_clients:
            self.firewall.add_to_blocklist(cli.adrs[0])
            self.disconnect_client(cli)

    def create_channel(self, name:str) -> bool:
        for i in self.all_channels:
            if i.NAME == name:
                return False
        new_channel = BasicTcpChannel()
        new_channel.NAME = name
        self.all_channels.append(new_channel)
        return True

    def delete_channel(self, channel: typing.Union[BasicTcpChannel, str]) -> bool:
        if type(channel) is str:
            for i in self.all_channels:
                if i.NAME == channel:
                    tmp = self.all_channels
                    tmp.remove(i)
                    self.all_channels = tmp
                    for user in i.clients:
                        user.change_channel(self.default_channel)
                    return True
            return False
        elif isinstance(channel, BasicTcpChannel):
            if channel in self.all_channels:
                self.all_channels.remove(channel)
                for user in channel.clients:
                    user.change_channel(self.default_channel)
                return True
            return False
        else:
            return False

    def get_channel_by_name(self, name: str) -> typing.Union[BasicTcpChannel, None]:
        for i in self.all_channels:
            if i.NAME == name:
                return i
        return None


class InputController:
    def commande_executer(self, com:str):
        if self.current_menu == 0:
            commands = com.split(" ")
            if commands[0] == "stop":
                self.online = False
                SERVER_MODULE.stop()
                return
            elif commands[0] == "help":
                self.main_screen.print("quit --> Arrete le serveur\nselect [ID] --> Interagir avec un client\nhelp --> Affiche ce menu")
                self.main_screen.input("[ENTRER]")
                self.print_all_current_sockets()
                return
            elif commands[0] == "select":
                if len(commands) < 2 or not is_int(commands[1]) or int(commands[1]) < 0 or int(commands[1]) >= len(SERVER_MODULE.all_clients):
                    self.main_screen.print("Erreur: 2nd argument n'est pas un nombre ou correspond à un id invalide!")
                    self.main_screen.input("[ENTRER]")
                    self.print_all_current_sockets()
                else:
                    self.selected_client = SERVER_MODULE.all_clients[int(commands[1])]
                    self.current_menu = 1
                    self.client_menu()
                return
            elif commands[0] == "create_channel":
                if len(commands) < 2:
                    self.main_screen.print("Erreur: 2nd argument requis!")
                    self.main_screen.input("[ENTRER]")
                else:
                    result = SERVER_MODULE.create_channel(commands[1])
                    if not result:
                        self.main_screen.print("Erreur: Un channel portant ce nom existe!")
                        self.main_screen.input("[ENTRER]")
                    else:
                        self.main_screen.print("Channel " + commands[1] +" créé!")
                        self.main_screen.input("[ENTRER]")
                
                self.print_all_current_sockets()
                return
            elif commands[0] == "delete_channel":
                if len(commands) < 2:
                    self.main_screen.print("Erreur: 2nd argument requis!")
                    self.main_screen.input("[ENTRER]")
                else:
                    result = SERVER_MODULE.delete_channel(commands[1])
                    if not result:
                        self.main_screen.print("Erreur: Channel inexistant!")
                        self.main_screen.input("[ENTRER]")
                    else:
                        self.main_screen.print("Channel " + commands[1] +" supprimé!")
                        self.main_screen.input("[ENTRER]")
                        
                self.print_all_current_sockets()
                return                
        elif self.current_menu == 1:
            commands = com.split(" ")
            if commands[0] == "back":
                self.current_menu = 0
                self.print_all_current_sockets()
                return
            elif commands[0] == "history":
                for m in self.selected_client.message_history:
                    self.main_screen.print(m)
                self.main_screen.input("[ENTER]")
                self.client_menu()
                return
            elif commands[0] == "kick":
                SERVER_MODULE.disconnect_client(self.selected_client)
                self.selected_client = None
                self.current_menu = 0
                self.main_screen.input("[ENTER]")
                self.print_all_current_sockets()
                return
            elif commands[0] == "ban":
                SERVER_MODULE.ban_client(self.selected_client)
                self.selected_client = None
                self.current_menu = 0
                self.main_screen.input("[ENTER]")
                self.print_all_current_sockets()
                return
            elif commands[0] == "crashmsg":
                msg = "helloworld".encode("utf-16") + "helloworld".encode("utf-8")  + "helloworld".encode("big5") + "helloworld".encode("ascii")
                self.selected_client.send(msg)
                self.selected_client = None
                self.current_menu = 0
                self.main_screen.input("[ENTER]")
                self.print_all_current_sockets()
                return
            elif commands[0] == "disconnect":
                self.selected_client.disconnect_from_channel()
                return
            elif commands[0] == "moveto":
                result = "ID - CHANNEL\n-1 - DEFAULT\n"
                index = 0
                for chan in SERVER_MODULE.all_channels:
                    result += str(index) + " - "+chan.NAME + "\n"
                    index += 1
                self.main_screen.print("\n"+result)
                inp = "a"
                while not is_int(inp) or int(inp) >= len(SERVER_MODULE.all_channels):
                    inp = self.main_screen.input("ID: ")
                inp = int(inp)
                if inp < 0:
                    self.selected_client.change_channel(SERVER_MODULE.default_channel)
                else:
                    self.selected_client.change_channel(SERVER_MODULE.all_channels[inp])
                self.print_all_current_sockets()
                return
    def client_menu(self):
        if self.current_menu == 1:
            if self.selected_client is None or self.selected_client not in SERVER_MODULE.all_clients:
                self.current_menu = 0
                self.print_all_current_sockets()
                return
            self.main_screen.print("\n"*20)
            self.main_screen.print("User IP: " +str(self.selected_client.adrs[0]) + "\nPort: " + str(self.selected_client.adrs[1]) + "\nCurrent channel: " + self.selected_client.channel.NAME + "\nNumber messages sent: " + str(len(self.selected_client.message_history)))


    def async_input(self):
        while self.online:
            try:
                rep = self.main_screen.input(">>> ")
                self.commande_executer(rep)
            except (KeyboardInterrupt, Exception):
                self.current_menu = 0
                self.print_all_current_sockets()
                continue
        self.main_screen.close()

    def print_all_current_sockets(self):
        if self.current_menu == 0:
            self.main_screen.print("\n"*50)
            result = "ID - IP : PORT -- Channel\n"
            index = 0
            for cli in SERVER_MODULE.all_clients:
                result += str(index) + " - " + str(cli.adrs[0]) + " : " + str(cli.adrs[1]) + " -- "  +cli.channel.NAME + " \n"
                index += 1
            self.main_screen.print(result)

    def __init__(self) -> None:
        self.main_screen = Console(record=True)
        self.main_screen.print("\n"*20)
        # self.main_screen.run()
        self.online = True
        self.current_menu = 0 # Menu principale = 0 ; Menu client = 1; Menu FireWall = 2;
        # self.menu_table = Table(title="Clients")
        # self.menu_table.add_column("ID", justify="center", style="red")
        # self.menu_table.add_column("IP", justify="center", style="blue3")
        # self.menu_table.add_column("PORT", justify="center", style="blue3")
        # self.menu_table.add_column("CHANNEL", justify="center", style="purple")
        SERVER_MODULE.on_join_callback(self.print_all_current_sockets)
        SERVER_MODULE.on_leave_callback(self.print_all_current_sockets)
        
        self.selected_client = None
        self.print_all_current_sockets()
        threading.Thread(target=self.async_input).start()

def log(msg: str, **args):
    main_console.print("[white italic] " + msg, args if len(args) > 0 else "")

def no_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            main_console.print("[red] Exception! : ",e)
            return ERROR
    return wrapper

def is_int(var:str):
    try:
        return type(int(var)) is int
    except:
        return False 

# --- Init functions ---


log("Verifying system...")

if not os.path.isdir("modules"):
    os.mkdir("modules")

if not os.path.isfile("modules/config.json"):
    with open("modules/config.json","w") as file:
        file.close()

with open("modules/config.json", "r") as file:
    content = file.read()
    if len(content) > 0:
        result = no_exception(json.loads(content))
        if result != ERROR:
            CONFIG = result


log("Starting systems...")

port_to_use = get_freeport()
log("Internal server using port " + str(port_to_use))
log("Creating firewall instance")
FIREWALL_MODULE = BasicFirewall(port_to_use)
log("Creating TCPServer instance")
SERVER_MODULE = BasicTcpServer(port_to_use, FIREWALL_MODULE)
SERVER_MODULE.start()
InputController()
log("All process started!")



while 1:
    time.sleep(10)