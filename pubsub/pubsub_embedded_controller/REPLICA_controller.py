#!/usr/bin/env python
# Copyright 2020-present Iman lotfimahyari.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import socket
import threading
import sys
import random
import struct
import time
from struct import pack as sp
from struct import unpack as su
from datetime import datetime as dt
from netifaces import ifaddresses
from scapy.all import get_if_list

## <<<<<<<< data structures >>>>>>>>>>>>>> #
server_address = ('', 65430)

REPLICA_sock = ""
my_name = "---"

nxt_NF_global_id = 5001
nxt_variable_global_id = 1
nxt_MW_global_id=1

global_name_NF_id = {}
global_name_variable_id = {}
global_name_MW_id = {}

NF_pub_global_ids = {} 

MW_sockets = [0] #  MW_GLOBAL_ID = Index of the [socket object of the correspondent MW , (address, port)]
thr_MW_sock_recv = [0] # MW_GLOBAL_ID = Index of the thread receiving on sockets connected to the MWs
thr_MW_sock_send = [0] # MW_GLOBAL_ID = Index of the threads sending on sockets connected to the MWs
thr_MW_sock_data_cleaner_handlr = [0] # MW_GLOBAL_ID = Index of the thread cleaning and handling msg received from MWs

MW_sock_input_queues = [0] # MW_GLOBAL_ID = Index of the queue for MW_sock_send
MW_sock_output_queues = [0] # MW_GLOBAL_ID = Index of the queue for MW_sock_recv
Main_received_queue = []

def msg_kind(kind_id):

    if kind_id==0:
        kind="INIT_NF_ID"
    elif kind_id==1:
        kind="INIT_PUB_ID"
    elif kind_id==2:
        kind="PUBLISH"
    elif kind_id==3:
        kind="SUB_REG"
    elif kind_id==4:
        kind="SUB_REM"
    elif kind_id==5:
        kind="VAR_ID_REQ"
    elif kind_id==6:
        kind="RECOVER"
    return kind

def REPLICA_log(func,the_log):

    fileName = "logs/REPLICA_Controller_log"
    with open(fileName,"a") as f:
        data ="["+str(dt.now())+"]  "+str(func)+"  "+str(the_log)+"\n"
        f.write(data)

def get_if(): # interface

    ifs=get_if_list()
    iface=None # "h1-eth0"
    for i in ifs:
        if "eth0" in i:
            iface=i
            break;
    if not iface:
        print "Cannot find eth0 interface"
        exit(1)
    return iface

def init_REPLICA(): # initializing the host ,MW_ID, pub_topic and Sub_topics
    global my_name, Main_received_queue, REPLICA_sock, server_address, nxt_MW_global_id

    my_src = ifaddresses(get_if())[2][0]['addr']
    num = int(my_src[-1:])
    my_name = "<REPLICA Controller> on H" + str(num)

    print "*********** START ****************"
    print "HOST name : {}".format(my_name)
    print "REPLICA controller STARTED"
    print "**********************************"
    REPLICA_log("[INIT] <init_REPLICA>"," REPLICA Controller in server H{}:  [STARTED]".format(str(num)))

    ## Create the TCP socket
    REPLICA_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    REPLICA_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # REPLICA_sock.setblocking(0)
    REPLICA_sock.bind(('',65430))
    print "REPLICA Controller is listening on requests......"
    REPLICA_log("[[INIT] <init_REPLICA>", "REPLICA Controller is listening on requests......")
    REPLICA_sock.listen(128)

    while True:
        conn, addr = REPLICA_sock.accept()
        MW_sockets.append(0)
        MW_sockets[nxt_MW_global_id]=[conn, addr]
        print "[INIT] MW ({}) : GLOBALY REGISTERED <=> MW_address = {}".format(nxt_MW_global_id, addr[:])
        REPLICA_log("[INIT] <init_conn_to_mw>","MW({}):GLOBALY REGISTERED <=> MW_address = {}".format(nxt_MW_global_id, addr[:]))
        thr_MW_sock_recv.append(0)
        thr_MW_sock_send.append(0)
        thr_MW_sock_data_cleaner_handlr.append(0)
        MW_sock_input_queues.append([])
        MW_sock_output_queues.append([])

        ## BUILDING AND STARTING 2 LIGHT THREADS FOR SEND AND RECEIVE ON THE MW SOCKET
        ## BUILDING THE MAIN THREAD DOING DATA CLEANING AND DISTRIBUTING (IF NEEDED) THE DATA RECEIVED FROM THE NF SOCKET
        thr_MW_sock_recv[nxt_MW_global_id]=threading.Thread(target=MW_sock_recv, args=[nxt_MW_global_id])
        thr_MW_sock_data_cleaner_handlr[nxt_MW_global_id]=threading.Thread(target=MW_sock_data_cleaner_handlr, args=[nxt_MW_global_id])
        thr_MW_sock_send[nxt_MW_global_id]=threading.Thread(target=MW_sock_send, args=[nxt_MW_global_id])
        thr_MW_sock_recv[nxt_MW_global_id].start()
        thr_MW_sock_data_cleaner_handlr[nxt_MW_global_id].start()
        thr_MW_sock_send[nxt_MW_global_id].start()
        nxt_MW_global_id += 1

def MW_sock_recv(MW_ID): # receiver function for the MW sockets
    global MW_sock_output_queues, MW_sockets

    print "[INFO] <MW_sock_recv> for MW({}) :[STARTED]".format(MW_ID)
    REPLICA_log("[INFO] <MW_sock_recv>", "               for MW({}) :[STARTED]".format(MW_ID))
    while True:
        try:
            raw_MW_received = MW_sockets[MW_ID][0].recv(1024)
            MW_sock_output_queues[MW_ID].append(raw_MW_received)
        except:
            raise

def MW_sock_send(MW_ID): # sender function for the MW sockets
    global MW_sock_input_queues, MW_sockets

    print "[INFO] <MW_sock_send>                for MW({}) :[STARTED]".format(MW_ID)
    REPLICA_log("[INFO] <MW_sock_send>", "               for MW({}) :[STARTED]".format(MW_ID))
    while True:
        try:
            out_msg = MW_sock_input_queues[MW_ID].pop(0)
            print "[MW][OUT]  <MW_sock_send>     => msg to MW ({}), len ({}), kind: ({})".format(MW_ID,su("H",out_msg[:2])[0],su("H",out_msg[2:4])[0])
            REPLICA_log("[MW][OUT]  <MW_sock_send>", "msg to MW ({},{}), len ({}), kind: ({})".format(MW_ID,su("H",out_msg[4:6])[0],su("H",out_msg[:2])[0],su("H",out_msg[2:4])[0]))
            MW_sockets[MW_ID][0].send(out_msg)
        except IndexError:
            time.sleep(1)
            pass
        except:
            raise

def MW_sock_data_cleaner_handlr(MW_ID):
    global MW_sock_input_queues, MW_sock_output_queues
    global nxt_NF_global_id, nxt_variable_global_id
    global NF_pub_global_ids, global_name_NF_id

    current_data = "" # empty for started
    print "[INFO] <MW_sock_data_cleaner_handlr> for MW({}) :[STARTED]".format(MW_ID)
    REPLICA_log("[INFO] <MW_sock_data_cleaner_handlr>", "for MW({}) :[STARTED]".format(MW_ID) )
    while True:
        try:
            # pop the first received chunk and add to the remained bytes (if any)
            current_data += MW_sock_output_queues[MW_ID].pop(0)

            # more than 2 bytes to know the lenght of the msg and enough bytes to rebuild a msg
            while (len(current_data)>2 and len(current_data)>=int(su("H",current_data[:2])[0])):
                in_msg = current_data[:int(su("H",current_data[:2])[0])] # we extract the msg from Data_length(2B)
                REPLICA_log("[MW][IN]  <MW_sock_data_cleaner_handlr>", "MSG len({}), kind({})".format(su("H",in_msg[:2])[0],
                        su("H",in_msg[2:4])[0]))
                print "[MW][IN] <MW_sock_data_cleaner_handlr>  => len({}), kind({})".format(su("H",in_msg[:2])[0],
                        su("H",in_msg[2:4])[0])

                #### INITIALIZING NF_ID REQUEST
                #### => (kind = 0)
                if int(su("H",in_msg[2:4])[0])==0:
                    REPLICA_log("[SW][IN] <handle_pkt_REPLICA> ", "INIT_NF_ID request msg received.")
                    print  "INIT_NF_ID REQUEST msg received."
                    global_name_NF_id["".join([su("c", x)[0] for x in in_msg[8:]])] = nxt_NF_global_id # mapping NF_NAME : NF_ID
                    NF_pub_global_ids[nxt_NF_global_id] = []
                    tmp_msg = in_msg[2:6]+sp("H",nxt_NF_global_id)+in_msg[8:]
                    tmp_msg = sp("H",len(tmp_msg)+2) + tmp_msg
                    MW_sock_input_queues[MW_ID].append(tmp_msg)

                    REPLICA_log("[MW][IN] <handle_pkt_REPLICA> ", "INIT_NF_ID reply msg sent.")
                    print "INIT_NF_ID REPLY msg sent."
                    nxt_NF_global_id += 1
                    #### CUT THE PROCESSED MSG FROM current_data
                    current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg

                ### INIT PUB_ID MSG
                ### (kind = 1)
                elif int(su("H",in_msg[2:4])[0])==1:
                    REPLICA_log("[SW][IN] <handle_pkt_REPLICA> ", "INIT_PUB_ID request msg received.")
                    print "INIT_PUB_ID request msg received."
                    global_name_variable_id["".join([su("c", x)[0] for x in in_msg[6:]])] = nxt_variable_global_id
                    NF_pub_global_ids[int(su("H",in_msg[4:6])[0])].append(nxt_variable_global_id)
                    tmp_msg = in_msg[2:6]+sp("H",nxt_variable_global_id)+in_msg[6:]
                    tmp_msg = sp("H",len(tmp_msg)+2) + tmp_msg
                    MW_sock_input_queues[MW_ID].append(tmp_msg)

                    REPLICA_log("[SW][IN] <handle_pkt_REPLICA> ", "INIT_PUB_ID reply msg sent.")
                    print "INIT_PUB_ID REPLY msg sent."
                    nxt_variable_global_id += 1
                    #### CUT THE PROCESSED MSG FROM current_data
                    current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg

                ### VARIABLE_ID request
                ### (kind = 5)
                elif int(su("H",in_msg[2:4])[0])==5:
                    REPLICA_log("[SW][IN] <handle_pkt_REPLICA> ","Variable_ID request msg received.")
                    print "Variable_ID request msg received."
                    var_name = "".join([su("c", x)[0] for x in in_msg[6:]])
                    if var_name in global_name_variable_id.keys():
                        tmp_msg = in_msg[2:6]+sp("H",global_name_variable_id[var_name])+in_msg[6:]
                        tmp_msg = sp("H",len(tmp_msg)+2) + tmp_msg
                        REPLICA_log("[SW][IN] <handle_pkt_REPLICA> ","Variable_ID reply msg sent.")
                        print "Variable_ID reply msg sent."
                    else:
                        tmp_msg = in_msg[2:6]+sp("H", 0)+in_msg[6:]
                        tmp_msg = sp("H",len(tmp_msg)+2) + tmp_msg
                        REPLICA_log("[SW][IN] <handle_pkt_REPLICA> ","Variable_ID reply (ERROR) msg sent.")
                        print "Variable_ID reply (ERROR) msg sent."
                    MW_sock_input_queues[MW_ID].append(tmp_msg)
                    #### CUT THE PROCESSED MSG FROM current_data
                    current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg

                ### RECOVER msg
                ### (kind = 6)
                elif int(su("H",in_msg[2:4])[0])==6:
                    REPLICA_log("[SW][IN] <handle_pkt_REPLICA> ", "RECOVER msg received.")
                    print "RECOVER msg : "
                    print in_msg
                    #### CUT THE PROCESSED MSG FROM current_data
                    current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg
        except:
            time.sleep(1)
            pass

def main():

    init_REPLICA()

if __name__ == '__main__':
    main()
