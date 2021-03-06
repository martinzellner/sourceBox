import server_communication_controller
import data_controller
import threading
import os
import socket
import logging

# @package sourceboxServer
# the server
#
# @author  Kai and Martin
#


class SourceBoxServer(object):

    # constants
    LOCK_TIME = 30

    # Creates a new instance of the SourceBoxServer
    def __init__(self):
        try:
            # delete old log file
            if os.path.exists("client.log"):
                os.remove("client.log")

            # Create the Data Controller
            self.data = data_controller.Data_Controller('./data/')

            # Contains all active Communication Controllers
            self.active_clients = dict()

            # Create socket
            self._create_socket()

            # create logger
            self.setupLogging(
                "server", logging.DEBUG)  # replace DEBUG by INFO for less output

            self.log.info('sourceBox server is running')

            self._command_loop(self.sock)

        # unexpected exit
        except KeyboardInterrupt:
            self.sock.close()
            del self.data
            for comm in self.active_clients.keys():
                self.active_clients[comm].send_close()
                self.log.debug('Remove ' + comm)
                self.remove_client(comm)
            self.log.info('Terminating SourceBoxServer')

    # Creates a socket
    # @author Martin Zellner
    def _create_socket(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(('', 50000))
        self.sock.listen(5)  # Max 5 Clients


    # When a new client connects
    # @param connection the connection object for the communication controller
    # @author Martin Zellner
    # @returns a communication controller
    def new_client(self, connection):
        # recieve init message from the client
        init_message = connection.recv(20).split(' ')

        if not init_message[0] == 'INIT':
            self.log.warning('Init failed')
        else:
            computer_name = init_message[1]
            self.log.info('A new client (' + computer_name +
                          ')logged in. Creating a Communication Controller')

            # Create a new communication_controller
            comm = server_communication_controller.Server_Communication_Controller(
                self, connection, computer_name)

            # add the communication controller to the active_clients list (to
            # keep track of all clients logged in)
            self.active_clients[computer_name] = comm

            # send all files to the client
            for current_file in self.data.list_dir():
                if not os.path.isdir(os.path.join(self.data.data_dir, current_file)) and ',v' not in current_file:
                    file_size = self.get_file_size(os.path.join(self.data.data_dir, current_file))
                    content = self.data.read_file(current_file)
                    comm.send_create_file(file_size, current_file, content)

            # log active clients
            self.log.info('Active Clients are:')
            self.log.info('\n'.join(self.active_clients.keys()))

    # removes a client
    # @author Martin Zellner
    # @param client the communication controller of the client
    def remove_client(self, computer_name):
        self.log.info('Remove client ' + computer_name)
        del self.active_clients[computer_name]

    # The server command loop
    # @param sock the socket to listen on
    def _command_loop(self, sock):
        while True:
            (connection, address) = sock.accept()
            self.new_client(connection)

    # Is called when a client creates a dir.
    # Creates the dir on all clients and in the data backend
    # @param path the path relative to the source box root
    # @param computer_name the name of the computer creating the file
    def create_dir(self, path, computer_name):

        self.log.debug(computer_name + ' created the dir ' + path)
        # create file in backend
        self.data.create_dir(path)

        # push changes to all other clients
        for comm in self.active_clients.keys():
            if not comm == computer_name:
                try:
                    self.active_clients[comm].send_create_dir(path)
                except IOError, err:
                    self.log.error('Error:' + str(err))
        # return true if successfully created
        return True

    # Is called when a client deletes a dir.
    # deletes the dir on all clients and in the data backend
    # @param path the path relative to the source box root
    # @param computer_name the name of the computer creating the file

    def delete_dir(self, path, computer_name):

        self.log.debug(computer_name + ' deleted the dir ' + path)
        # create file in backend
        self.data.delete_dir(path)

        # push changes to all other clients
        for comm in self.active_clients.keys():
            if not comm == computer_name:
                try:
                    self.active_clients[comm].send_delete_dir(path)
                except IOError, err:
                    self.log.error('Error:' + str(err))
        # return true if successfully created
        return True

    # Is called when a client creates a file.
    # Creates the file on all clients and in the data backend
    # @param path the path relative to the source box root
    # @param file_name the file name
    # @param content the content of the file
    # @param computer_name the name of the computer creating the file
    def create_file(self, file_path, file_size, computer_name, content=''):

        self.log.debug('Creating the file ' + file_path)
        # create file in backend
        self.data.create_file(file_path, computer_name, content)

        # push changes to all other clients
        for comm in self.active_clients.keys():
            if not comm == computer_name:
                try:
                    self.active_clients[comm].send_create_file(
                        file_size, file_path, content)
                except IOError, err:
                    self.log.error('Error:' + str(err))
        # return true if successfully created
        return True

    # Is called when a client locks a file.
    # Locks the file in the backend
    # @param path the path relative to the source box root
    # @param file_name the file name
    def lock_file(self,file_path, computer_name):
        self.data.lock_file(file_path, computer_name)

        # push changes to all other clients
        for comm in self.active_clients.keys():
            if not comm == computer_name:
                self.active_clients[comm].send_lock_file(file_path)

                # set Timer to LOCK_TIME in sec for auto unlock
                threading.Timer(self.LOCK_TIME, self.active_clients[
                                comm].send_unlock_file, (file_path,)).start()

        # return true if successfully locked
        return True

    # Is called when a client unlocks a file.
    # Unlocks the file in the backend
    # @param path the path relative to the source box root
    # @param file_name the file name
    def unlock_file(self, file_path, computer_name):
        self.data.unlock_file(file_path, computer_name)

        # push changes to all other clients
        for comm in self.active_clients.keys():
            if not comm == computer_name:
                try:
                    self.active_clients[comm].send_unlock_file(file_path)
                except IOError, err:
                    self.log.error('Error:' + str(err))
        # return true if successfully unlocked
        return True

    # Is called when a client changes a file.
    # Updates the file on all clients and in the data backend
    # @param path the path relative to the source box root
    # @param file_name the file name
    def modify_file(self, file_path, content, computer_name):
        self.data.modify_file(file_path, content, computer_name)

        # push changes to all other clients
        for comm in self.active_clients.keys():
            if not comm == computer_name:
                file_size = self.data.get_file_size(file_path)
                try:
                    self.active_clients[comm].send_modify_file(
                        file_size, file_path, content)
                except IOError, err:
                    self.log.error('Error:' + str(err))
        # return true if successfully modified
        return True

    # Is called when a client deletes a file.
    # Deletes the file on all clients and in the data backend
    # @param path the path relative to the source box root
    # @param file_name the file name
    def delete_file(self, file_path, computer_name):
        # return true if successfully deleted
        self.data.delete_file(file_path, computer_name)

        # push changes to all other clients
        for comm in self.active_clients.keys():
            if not comm == computer_name:
                try:
                    self.active_clients[comm].send_delete_file(file_path)
                except IOError, err:
                    self.log.error('Error:' + str(err))
        # return true if successfully deleted
        return True

    # gets the size of a file
    # @param path the path relative to the source box root
    # @param file_name the file name
    def get_file_size(self, file_path):
        if os.path.exists(file_path):
            return os.path.getsize(file_path)
        else:
            return False
    # Moves a file
    def move(self, old_file_path, new_file_path, computer_name):
        # return true if successfully deleted
        self.data.move(old_file_path, new_file_path)

        # push changes to all other clients
        for comm in self.active_clients.keys():
            if not comm == computer_name:
                try:
                    self.active_clients[comm].send_move(old_file_path, new_file_path)
                except IOError, err:
                    self.log.error('Error:' + str(err))
        # return true if successfully deleted
        return True

    # creates global log object
    # @param name the name of the logger
    # @param level level of logging e.g. logging.DEBUG
    # @author Emanuel Regnath

    def setupLogging(self, name, level):
        self.log = logging.getLogger(name)
        self.log.setLevel(level)

        formatter = logging.Formatter('[%(levelname)s] %(message)s')

        sh = logging.StreamHandler()
        sh.setLevel(level)
        sh.setFormatter(formatter)
        self.log.addHandler(sh)

        fh = logging.FileHandler(name + ".log")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        self.log.addHandler(fh)
