# -*- coding: utf-8 -*-#
# sourceboxclient – Client_Communication_Controller
# handles the communication with the server
#
# @encode:  UTF-8, tabwidth = , newline = LF
# @author:  Paul

import socket
import threading
import logging
from urllib import pathname2url, url2pathname 

class Client_Communication_Controller(object):

    # command constants
    COMMAND_SENDCREATEFILE = 'CREATE_FILE'
    COMMAND_SENDLOCKFILE = 'LOCK'
    COMMAND_SENDUNLOCKFILE = 'UNLOCK'
    COMMAND_SENDDELETEFILE = 'REMOVE'
    COMMAND_SENDMODIFYFILE = 'MODIFY'
    COMMAND_MOVE = 'MOVE'
    COMMAND_SENDCREATEDIR = 'CREATE_DIR'
    COMMAND_DELETEDIR = 'DELETE_DIR'
    COMMAND_INIT = 'INIT'
    COMMAND_ACK = "OK\n"

    # Constructor
    # @param ip the ip of the server to connect to
    # @param port the port of the server
    # @param computer_name name of the client
    # @author Martin Zellner
    def __init__(self, parent, ip, port, computer_name):

        # catch logging object
        self.log = logging.getLogger("client")

        # store the computer name in an instance variable
        self.computer_name = computer_name
        self.parent = parent
        self.gui = parent.gui

        # Creates the instance variable sock. This is the socket communicating
        # with the server
        self.controller_socket = self._open_socket(ip, port)

        # Inits the connection
        self._init_connection()

        # Starts a thread listening for server events
        threading_queue = []
        self.command_listener_thread = Command_Recieve_Handler(
            'Communication_Controller Thread for listening', self.controller_socket, self.parent)
        # daemonize thread. This makes sure that it does not prevent the Client
        # Prozess from terminating (e.g. on a Keyboard interrupt)
        self.command_listener_thread.daemon = True
        threading_queue.append(self.command_listener_thread)
        self.command_listener_thread.start()

        self.log.info('Client Created Communication_Controller')

    # Deconstructor
    # @author Martin Zellner
    def __del__(self):
        # Closes the socket when the instance is destructed
        try:
            self.command_listener_thread.stop()
            self._close_socket(self.controller_socket)

        except AttributeError:
            self.log.warning(
                'Could not close socket. Propably the socket was not open in the first place.')

    # Initialises the connection and identifies the client to the server
    # @author Martin Zellner
    def _init_connection(self):
        self.controller_socket.send(
            self.COMMAND_INIT + ' ' + self.computer_name)

    # Sends a command to the server that creates a file with content
    # @author Paul
    # @param filePath of the new file related to sourceBox, size, content
    # @return boolean
    def send_create_file(self, filePath, size, content):
        return self._send_command_with_content(self.COMMAND_SENDCREATEFILE, filePath, size, content)

    # Sends a command to the server that modiry a file with new content
    # @author Paul
    # @param filePath of the new file related to sourceBox, size, content
    # @return boolean
    def send_modify_file(self, filePath, size, content):
        return self._send_command_with_content(self.COMMAND_SENDMODIFYFILE, filePath, size, content)

    # Sends a command to the server (without content)
    # @throws IOError if a timeout occurs
    # @author Martin Zellner
    # @param command the command
    # @param file_path path to the file
    # @returns boolean
    def _send_command(self, command, file_path):
        try:
            # create message
            message = command + ' ' + pathname2url(file_path)
            # send message
            self.controller_socket.send(message)

            # Wait for the recieve thread to send us a ok Event
            status = self.command_listener_thread.ok.wait(8.0)
            self.command_listener_thread.ok.clear()
            if not status:
                raise IOError('Did not recieve a response from the server.')

            # if no error was raised
            return True
        except IOError:
            self.gui.errorBox(
                'Error', '[ERROR] Timeout: Did not recieve a response from the server.')
            self.log.error(
                'Timeout: Did not recieve a response from the server.')

    # Sends a command to the server (with content)
    # @throws IOError if a timeout occurs
    # @author Martin Zellner
    # @param command the command
    # @param file_path path to the file
    # @param content the content of the file
    # @returns boolean
    def _send_command_with_content(self, command, filePath, size, content):
        try:
            # create message
            message = command + ' ' + str(size) + ' ' + pathname2url(filePath)

            # send message
            self.controller_socket.sendall(message)

            # Wait for the recieve thread to send us a ok Event
            status = self.command_listener_thread.ok.wait(8.0)
            self.command_listener_thread.ok.clear()
            if not status:
                raise IOError('Did not recieve a response from the server.')

            # Send the content
            self.controller_socket.send(content)

            # Wait for the recieve thread to send us a ok Event
            status = self.command_listener_thread.ok.wait(8.0)
            self.command_listener_thread.ok.clear()
            if not status:
                raise IOError('Did not recieve a response from the server.')

            return True
        except IOError:
            self.gui.errorBox(
                'Error', '[ERROR] Timeout: Did not recieve a response from the server.')
            self.log.error(
                'Timeout: Did not recieve a response from the server.')

    # Sends a lock command to the server
    # @author Paul
    # @param file_path path of the file related to sourceBox root
    # @return boolean
    def send_lock_file(self, file_path):
        return self._send_command(self.COMMAND_SENDLOCKFILE, file_path)

    # Sends a unlock command to the server
    # @author Paul
    # @param file_path path of the file related to sourceBox root
    # @returns a boolean
    def send_unlock_file(self, file_path):
        return self._send_command(self.COMMAND_SENDUNLOCKFILE, file_path)

    # Sends a delete command to the server
    # @author Paul
    # @param file_path path of the file related to sourceBox root
    # @returns boolean
    def send_delete_file(self, file_path):
        return self._send_command(self.COMMAND_SENDDELETEFILE, file_path)

    # Sends a create diractory command to the server
    # @author Paul
    # @param file_path path of the dir related to sourceBox root
    # @returns boolean
    def send_create_dir(self, path):
        return self._send_command(self.COMMAND_SENDCREATEDIR, path)

    # Sends a delete dir command to the server
    # @author Martin
    # @param file_path path of the dir related to sourceBox root
    # @returns boolean
    def send_delete_dir(self, path):
        return self._send_command(self.COMMAND_DELETEDIR, path)

    # Sends a move file command to the server
    # @author Martin
    # @param old_path path of the file
    # @param new_path new path of the file
    # @returns a boolean
    # @throws IOError if a timeout occurs
    def send_move(self, src_path, dest_path):
        try:
            mess = self.COMMAND_MOVE + ' ' + pathname2url(src_path) + ' '  + pathname2url(dest_path)
            self.controller_socket.send(mess)

            # Wait for the recieve thread to send us a ok Event
            status = self.command_listener_thread.ok.wait(8.0)
            self.command_listener_thread.ok.clear()
            if not status:
                raise IOError('Did not recieve a response from the server.')

            return True
        except IOError:
            self.gui.errorBox(
                'Error', 'Timeout: Did not recieve a response from the server.')
            self.log.error(
                'Timeout: Did not recieve a response from the server.')

    # Opens a socket
    # @param ip the ip of the server to connect to
    # @param port the port of the server
    # @returns a socket
    def _open_socket(self, ip, port):
        try:
            sock = socket.socket()
            sock.connect((ip, port))
            return sock
        except socket.error, e:
            if e.errno == 61:
                self.gui.errorBox(
                    'Error', '[ERROR] Server is not reachable. Please check your configuration.')
                self.log.error(
                    'Server is not reachable. Please check your configuration.')
                exit()
            else:
                raise e

    # Closes the socket
    # @param sock the socket to close
    def _close_socket(self, sock):

        sock.send('CLOSE')
        self.log.debug('sending close')
        # Wait for the recieve thread to send us a ok Event
        status = self.command_listener_thread.ok.wait(8.0)
        self.command_listener_thread.ok.clear()
        if not status:
            raise IOError('Did not recieve a response from the server.')

        sock.close()
        self.log.debug('Connection closed.')


# Thread that listens for commands on the incoming connection. If it recieves a "OK\n" it sends a 'ok'- Event
# @author Martin Zellner
class Command_Recieve_Handler(threading.Thread):
    COMMAND_ACK = "OK\n"
    COMMAND_CREATE = "CREATE"
    COMMAND_DELETEFILE = "REMOVE"
    COMMAND_MODIFYFILE = "MODIFY"
    COMMAND_LOCKFILE = "LOCK"
    COMMAND_UNLOCKFILE = "UNLOCK"
    COMMAND_DELETE_DIR = "DELETE_DIR"
    COMMAND_CREATE_DIR = "CREATE_DIR"
    COMMAND_MOVE = "MOVE"

    def __init__(self, thread_name, open_socket, parent):
        threading.Thread.__init__(self)

        # Write function variables to instance variables of the handler class
        self.thread_name = thread_name
        self.open_socket = open_socket
        self.parent = parent
        self.log = logging.getLogger("client")

        # Create 'ok' Event
        self.ok = threading.Event()
        self.error = threading.Event()

        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        self.log.info('[' + self.thread_name + '] ' + 'Created')

        # endless loop to recieve commands
        while not self._stop:
            # split the recieved data
            try:
                data = self.open_socket.recv(1024).split(' ')
            except Exception, err:
                self.log.error(str(err))

            if data[0] == self.COMMAND_ACK:  # If a OK command was recieved
                # Fire the 'ok' Event
                self.ok.set()
            elif data[0] == 'ALREADY_LOCKED':
                self.error.set('ALREADY_LOCKED')
            elif data[0] == self.COMMAND_CREATE:  # if a create command was recieved (when other clients changed the folder)
                self.log.debug('Recieved Create Command' + str(data))
                self.open_socket.send('OK\n')

                file_size = int(data[1])
                file_path = url2pathname(data[2])
                #self.log.debug(self.parent.fs.ignoreModify)
                # read data from the socket
                if not file_size == 0:
                    content = ''
                    while file_size > len(content):
                        data = self.open_socket.recv(1024)
                        if not data:
                            break
                        content += data

                    self.open_socket.send('OK\n')
                    self.parent.fs.createFile(file_path, content)
                else:
                    self.parent.fs.createFile(file_path, '')


            elif data[0] == self.COMMAND_DELETEFILE:
                self.log.debug('Recieved Delete Command' + str(data))

                file_path = url2pathname(data[1])
                self.open_socket.send('OK\n')

                self.parent.fs.deleteFile(file_path)

            elif data[0] == self.COMMAND_MODIFYFILE:
                self.log.debug('Recieved Modify Command' + str(data))
                self.open_socket.send('OK\n')

                file_size = int(data[1])
                file_path = url2pathname(data[2])

                # read data from the socket
                if not file_size == 0:
                    content = ''
                    while file_size > len(content):
                        data = self.open_socket.recv(1024)
                        if not data:
                            break
                        content += data
                    self.open_socket.send('OK\n')
                    self.parent.fs.writeFile(file_path, content)

            elif data[0] == self.COMMAND_LOCKFILE:
                self.log.debug('Recieved Lock Command' + str(data))

                file_path = url2pathname(data[1])
                self.open_socket.send('OK\n')

                self.parent.fs.lockFile(file_path)

            elif data[0] == self.COMMAND_UNLOCKFILE:
                self.log.debug('Recieved Unlock Command' + str(data))

                file_path = url2pathname(data[1])
                self.open_socket.send('OK\n')

                self.parent.fs.unlockFile(file_path)
            elif data[0] == self.COMMAND_CREATE_DIR:
                self.log.debug('Recieved COMMAND_CREATE_DIR' + str(data))

                file_path = url2pathname(data[1])
                self.open_socket.send('OK\n')

                self.parent.fs.createDir(file_path)
            elif data[0] == self.COMMAND_DELETE_DIR:
                self.log.debug('Recieved COMMAND_DELETE_DIR' + str(data))

                file_path = url2pathname(data[1])
                self.open_socket.send('OK\n')

                self.parent.fs.deleteDir(file_path)
            elif data[0] == self.COMMAND_MOVE:
                self.log.debug('Recieved COMMAND_MOVE' + str(data))

                src_path = url2pathname(data[1])
                dest_path = url2pathname(data[2])

                self.open_socket.send('OK\n')

                self.parent.fs.moveFileDir(src_path, dest_path)

            elif data[0] == 'CLOSE\n':
                try:
                    self.open_socket.send('OK\n')
                    self.open_socket.close()
                except Exception, err:
                    self.log.error(str(err))
                    self.parent.gui.changeStatus()
            else:
                self.log.debug('Command recieved' + str(data))
