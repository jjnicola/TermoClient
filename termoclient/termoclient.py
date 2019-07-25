import sys, getopt
import signal, os
import socket
import select
import traceback
import time
from daemonize import Daemonize
import logging

from termoclient.termomodule import  TermoSql, TermoComm

logger = logging.getLogger(__name__)

VERSION = "Termostato Client v0.1"
pid = "/tmp/termoclient.pid"
server_address = '/tmp/termoclient.sock'



def client(dev_set):
    # Create a UDS socket
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    # Connect the socket to the port where the server is listening
    sys.stderr.write ('connecting to %s\n' % server_address)
    try:
        sock.connect(server_address)
    except socket.error:
        sys.exit(1)

    try:
        # Send data
        sys.stderr.write ('Sending "%s"\n' % dev_set)
        sock.sendall(dev_set.encode("utf-8"))

        amount_received = 0
        amount_expected = len(dev_set.encode("utf-8"))

        while amount_received < amount_expected:
            data = sock.recv(16)
            amount_received += len(data)
            sys.stderr.write ('Received "%s" successfully\n' % data.decode())
            time.sleep(1)
    finally:
        sys.stderr.write ('Closing socket. Bye bye!\n')
        sock.close()


def kill_server(dbconn, devsoc, sock):
    dbconn.close()
    devsoc.close()
    sock.close()
    try:
        logger.debug("Old socket removed")
        os.unlink(server_address)
    except OSError:
        if os.path.exists(server_address):
            logger.debug("Not possible to delete the old socket.")
    logger.debug("Server Killed")
    sys.exit(0)

def open_server_sock():
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setblocking(0)

    # Bind the socket to the port
    logger.debug ("Starting up on %s.", server_address)
    sock.bind(server_address)

    # Listen for incoming connections
    sock.listen(5)
    return sock

def check_for_client(sock, read_list, newcontroller):
    readable, writable, errored = select.select(read_list, [], read_list, 10)
    for s in readable:
        if s is sock:
            client_socket, address = sock.accept()
            client_socket.setblocking(0)
            read_list.append(client_socket)
            logger.debug ("Client connected.")
        else:
            recv_cmd = s.recv(1024)
            if recv_cmd:
                logger.debug ("Server recv: %s", recv_cmd.decode('UTF-8'))
                if recv_cmd.decode() == "KILLSERVER":
                    logger.debug ("Kill requested.")
                    s.send(recv_cmd)
                    kill_server(dbconn, soc, sock)

                elif recv_cmd.decode() in "GetSetup":
                    ret = newcontroller.GetSetup(soc)
                    if ret:
                        logger.debug ("Configuration received." + ret)
                        s.send(recv_cmd)
                    else:
                        logger.debug ("Error sending configuration.")
                elif "STY:" in recv_cmd.decode():
                    ret = newcontroller.SetDev(soc, recv_cmd.decode())
                    if ret:
                        logger.debug ("New configuration sent.")
                        s.send(recv_cmd)
                    else:
                        logger.debug ("Error sending configuration.")
                        recv_cmd = None
                else:
                    s.close()
                    read_list.remove(s)

    # Handle exceptional conditions"
    for s in errored:
        print ('handling exceptional condition for', s.getpeername())
        # Stop listening for input on the connection
        read_list.remove(s)
        s.close()

def mainloop(host, batch_number):

    logger.debug("main loop")
    logger.debug(host)
    newcontroller = TermoComm(logger)
    soc = False
    while soc is False:
        try:
            logger.debug("trying to connect")
            soc = newcontroller.NewConn(host)
        except:
            logger.debug("ERROR: error en la clase TermoComm")
            continue
        logger.debug("soc: %s", str(soc))

    ret = False
    while ret is False:
        try:
            ret = newcontroller.InitController(soc)
            logger.debug("controller initialized: ")
        except:
            logger.debug("ERROR: error en la clase TermoComm")

    logger.debug("Starting data logging.")

    dbconn = False
    while dbconn is False:
        try:
            sqlquery = TermoSql(logger)
            dbconn = sqlquery.NewDB()
            logger.debug("Connected to the DB: %s", str(dbconn))
            batch_id = sqlquery.Getbidfrombnumber(dbconn, batch_number)
            if batch_id is None:
                logger.debug("Impossible to find a batch_id for the batch number %s",
                             str(batch_number))
                sys.exit(1)
            else:
                msg = ("Starting to log data for the batch number #" +
                      str(batch_number) + " (id" + str(batch_id) + ")" )
                logger.debug(msg)
        except:
            logger.debug("ERROR: Not possible to connect to the DB.")

        # Make sure the socket does not already exist
        try:
            os.unlink(server_address)
        except OSError:
            if os.path.exists(server_address):
                raise

    # Create a UDS socket
    sock = open_server_sock()
    read_list = [sock]

    #Start Infinite loop
    while True:
        data = False
        try:
            data = newcontroller.GetLog(soc)
            logger.debug("Retrieved data: %s", str(data))
        except:
            logger.debug("ERROR: Connection error. Not possible to retrive data.")

        try:
            if data is not False:
                sqlquery.SaveData(dbconn, data, batch_id)
        except:
            logger.debug("ERROR: Not possible to save data in the DB. Retrying in 10 seconds.")

        # Check for client connection to set the device.
        check_for_client(sock, read_list, newcontroller)

def help():
    '''Print the help.'''
    print (VERSION)
    print ("")
    print ("\t-h <ip-address> | --host=<ip-address>              : IP address of the device.")
    print ("\t-n <new-batch-name> | --new-batch=<new-batch-name> : It creates a new Batch in the database with given name.")
    print ("\t-b <batch-number> | --batch-number=<batch-number>  : Batch's number. Usefull to reconnect in case of problem and continuing loading, or the number for the new batch.")
    print ("\t-s <style-name> | --style=<style-name>             : It style name for the new batch .")
    print ("\t-H | --help                                        : This help.")
    print ("\t-V | --version                                     : Show version.")
    print ("\t-v | --verbose                                     : Verbose enabled.")
    print ("\t-f | --foreground                                  : Not daemonize. Keep in foreground for debugging pourposes.")
    print ("\t-k | --kill-server                                 : Kill the server in a clean way.")
    print ("\t-g | --get-setuo                                   : Get the current setup configuration in device.")
    print ("")
    print ("\t-c <dev config> | --config=<dev-config>            : Set the device to a beer profile with predefined temperatures")
    print ("                                                       or a custom one. Also to reset the device.")
    print ("\t List of profiles: ")
    print ("\t\t 0 = MADURACION 0C")
    print ("\t\t 1 = LAGER 10C")
    print ("\t\t 2 = KOLSCH 15C")
    print ("\t\t 3 = SCOTTISH 16C")
    print ("\t\t 4 = ENGLISH 18C")
    print ("\t\t 5 = WEIZEN 19C")
    print ("\t\t 6 = BELGA 20C")
    print ("\t\t 7 = CUSTOM 0-25C")
    print ("")
    print ("\t\t Example 1: for a belga profile: --config STY:006")
    print ("\t\t Example 2: for a Maduration profile: --config STY:000")
    print ("\t\t Example 3: to reset de device: --config RST:000")
    print ("\t\t Example 4: for a custom Temp 18.5C: --config TMP:185")
    print ("")


def main(argv=sys.argv[1:], server=True):

    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    fh = logging.FileHandler("/tmp/termoclient.log", "w")
    fh.setFormatter(formatter)
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    keep_fds = [fh.stream.fileno()]

    try:
        opts, args = getopt.getopt(
                argv,
                "h:n:b:s:HVvgfc:k",
                ["host=",
                 "new-batch=",
                 "style=",
                 "batch-number=",
                 "help",
                 "verbose",
                 "version",
                 "get-setup",
                 "foreground",
                 "config=",
                 "kill-server"]
        )
    except getopt.GetoptError:
        print ('Error in given arguments. Try datawriter.py -H|--help for help.')
        sys.exit(2)

    verbose = False
    new_batch = False
    style = False
    batch_number = False
    host = False
    foreground = False
    cli_cmd = None
    killserver = False
    for o, a in opts:
        if o in ("-H", "--help"):
            help ()
            sys.exit()
        elif o in ("-V", "--version"):
            print (VERSION)
            sys.exit()
        elif o in ("-v", "--verbose"):
            verbose = True
        elif o in ("-n", "--new-batch"):
            new_batch = a
        elif o in ("-s", "--style"):
            style = a
        elif o in ("-b", "--batch-number"):
            batch_number = a
        elif o in ("-h", "--host"):
            host = a
        elif o in ("-f", "--foreground"):
            foreground = True
            print ("The process will not be demonized for debugging pourposes.")
        elif o in ("-c", "--config"):
            cli_cmd = a
        elif o in ("-g", "--get-setup"):
            cli_cmd = "GetSetup"
        elif o in ("-k", "--kill-server"):
            killserver = True


    # Check if it is already running.
    if os.path.exists(server_address):
        if killserver is True:
            client ("KILLSERVER")
            sys.exit(0)

        if not cli_cmd:
            print ("ERROR: Arguments needed to set the device.")
            print("If you think this is an error, look for a running process, socket file or pid file")
            sys.exit(1)

        client(cli_cmd)
        sys.exit(0)

    if host is False:
        print ("ERROR: I need the host name or an IP address.")
        print ("Remember to give a batch id or create a new batch.")
        print ("\ndatawriter.py -H|--help for more info.\n")
        sys.exit()

    sqlquery = TermoSql(logger)
    dbconn = sqlquery.NewDB()
    if batch_number is False and new_batch is False:
        print ("ERROR: Missing arguments.");
        print ("Hint: Run the program with a batch id to add log data to the current batch:");
        print ("\tThe last batch id is " + str(sqlquery.GetLastBatchNumber(dbconn)))
        print ("Or create a new batch.")
        print ("\nFor more info run the program with -H or --help option.\n")
        sys.exit()

    if batch_number is not False:
        isbatchid = sqlquery.CheckBatchNumber(dbconn, batch_number)

    if new_batch is not False:
        if batch_number is False:
            batch_number = sqlquery.GetLastBatchNumber(dbconn) + 1
        elif isbatchid is True:
            print ("ERROR: the given batch number exist and it can not be aplied to a new batch.")
            sys.exit()

        if style is False:
            style = "default"
        print ("\nThe new batch will be created in the database with the following information:")
        print ("\tBatch ID:\t" + str(batch_number))
        print ("\tBatch Name:\t" + new_batch)
        print ("\tBatch Style:\t" + style)

        answer = ""
        while (answer not in ("y","n")):
            print ("Is this information right? (y/n)")
            answer = sys.stdin.read(1)

        if answer.lower() == "y":
            sqlquery.CreateNewBatch(dbconn, new_batch, batch_number, style)
            print ("The new batch was created")
        elif answer.lower() == "n":
            print ("Batch creation aborted. Bye bye!")
            sys.exit()
    elif isbatchid is False:
        print ("ERROR: the given batch number does not exist. \
                Please give a right one or create a new batch.")
        sys.exit()
    elif isbatchid is True:
        answer = ""
        while (answer not in ("y","n")):
            print ("Are you sure you want to add log entries to "+
                    "the batch number " + str(batch_number) +"? (y/n)")
            answer = sys.stdin.read(1)
        if answer.lower() == "n":
            print ("Bye bye!")
            sys.exit()

    print ("Starting")
    sqlquery.CloseDB(dbconn)
    if foreground is True:
        newdaemon = Daemonize(app="termoclient",
                              pid=pid,
                              action=None,
                              keep_fds=keep_fds,
                              foreground=True,
                              verbose=True,
                              chdir = os.getcwd())

    else:
        newdaemon = Daemonize(app="termoclient",
                              pid=pid,
                              action=None,
                              keep_fds=keep_fds,
                              foreground=False,
                              verbose=True,
                              chdir = os.getcwd())
    newdaemon.start()
    mainloop(host, batch_number)


if __name__ == "__main__":
    main()
