""" Classes for creating UDP or TCP Connections """
import config
import socket

""" UDPConn"""
class UDPConn:
    def __init__(self, bind_address):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(bind_address)

    def receive(self, buffer_size=1024):
        data, address = self.sock.recvfrom(buffer_size)
        data, address = self.sock.recvfrom(config.listenAddress)
        return data, address

    def send(self, message, destination_address):
        self.sock.sendto(message.encode(), destination_address)

    def close(self):
        self.sock.close()

""" TCPConn """

class TCPConn:
    def __init__(self, bind_address):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(bind_address)

    def send(self, message):
        self.sock.sendall(message.encode())

    def receive(self, buffer_size=1024):
        data = self.sock.recv(buffer_size)
        return data.decode()

    def close(self):
        self.sock.close()
""" Usage """
"""
conn = UDPConn(('localhost', bind_address))

# Receive data
data, address = conn.receive()
print('Received data:', data.decode())
print('Sender address:', address)

# Send data
message = 'Hello, UDP!'
destination_address = ('localhost', 54321)
conn.send(message, destination_address)

# Create a TCP connection
conn = TCPConn(('localhost', bind_address))

# Send data
message = 'Hello, TCP!'
conn.send(message)

# Receive data
data = conn.receive()
print('Received data:', data)

# Close the connection
conn.close()
"""