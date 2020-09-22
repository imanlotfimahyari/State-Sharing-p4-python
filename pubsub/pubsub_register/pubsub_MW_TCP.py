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


'''
    Uncommenting the print commands next to the "mid_log"s 
    can give a simple screen view of message transactions.
''' 
import socket
import threading
import sys
import os
import time
import random
import struct
from struct import pack as sp
from struct import unpack as su
from datetime import datetime as dt
import copy
from netifaces import ifaddresses
from scapy.all import get_if_list

# <<<<<<<< data structures >>>>>>>>>>>>>> #
my_server_name = "-" # my server name e.g. H1

nxt_VNF_local_id = 1
VNF_local_global_id = [0] # VNF_LOCAL_ID = Index of the VNF_GLOBAL_ID

rcv_mw_socks = [0]
REPLICA_sock = 0 # The socket object of the connection between the Middle_Ware and the REPLICA controller
VNF_sockets = [0] #  VNF_LOCAL_ID = Index of the [socket object of the correspondent VNF , (address, port)]
rcv_mw_sock_multi = {} # var_id: socket object for listenig on the multicast server socket,regarding to that var_id

all_mcast_groups = []
mcast_groups = [0]

thr_VNF_sock_recv = [0] # VNF_LOCAL_ID = Index of the thread receiving on sockets connected to the VNFs
thr_VNF_sock_send = [0] # VNF_LOCAL_ID = Index of the threads sending on sockets connected to the VNFs
thr_VNF_sock_data_cleaner_handlr = [0] # VNF_LOCAL_ID = Index of the thread cleaning and handling msg received from VNFs
thr_rcv_pub_multi = {} # var_id: thread object for listenig on the multicast server socket,regarding to that var_id

VNF_subscriptions = {} # subscribed variable_IDs : [subscribed VNF_GLOBAL_IDs]
VNF_publishes = {}     # VNF_GLOBAL_ID : [publishing variable_IDs]

VNF_sock_input_queues = [0]  # VNF_LOCAL_ID = Index of the queue for VNF_sock_send
VNF_sock_output_queues = [0] # VNF_LOCAL_ID = Index of the queue for VNF_sock_recv

OUT_2_queue = [] # my queue for msgs from the inside of the server
IN_1_queue = []  # my queue for msgs from the
OUT_1_queue = [] # my queue for msgs from the


'''### Basic FUNCTIONS ###'''
def mid_log(func,the_log): # Log recording for Middle_Ware
    global my_server_name

    fileName = "logs/middleware_"+str(my_server_name)
    with open(fileName,"a") as f:
        data ="["+str(dt.now())+"] "+str(func)+"  "+str(the_log)+"\n"
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

def pubSubIP(var_id, kind): # making IP.destination based on variable_id and packet kind
    if kind in [0,1,5,6]:# "INIT_VNF_ID","INIT_PUB_ID", "Variable_ID_REQ", "RECOVER"
        b=[10,0,4,4]
    else:
        a=bin(var_id)[2:].zfill(32)
        b=[int(a[8*i:8*(i+1)],2) for i in range(4)]
        b[0]=239
        if kind==2: # "PUBLISH"
            b[1]=b[1]
        elif kind==3: # "SUBSCRIBE"
            b[1]=b[1]|192
        elif kind==4: # "UNSUBSCRIBE"
            b[1]=b[1]|128

    special_IP=".".join([str(c) for c in b])
    return special_IP

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

########################
###### INT MODULE ######
########################

'''### VNF <==> MW ###'''
def init_conn_to_VNF(): # Initializing  the Middle_Ware, making general server listening for VNF connections
    global my_server_name, nxt_VNF_local_id, VNF_local_global_id, VNF_sockets
    global thr_VNF_sock_recv, thr_VNF_sock_send, thr_VNF_sock_data_cleaner_handlr

    mid_log("[INIT] <init_conn_to_VNF>", "HOST name: {}, Middle_Ware :[STARTED]".format(my_server_name))
    INIT_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    INIT_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # INIT_sock.setblocking(0)
    INIT_sock.bind(("localhost",65431))
    print "[INIT] General server listening..."
    mid_log("[INIT] <init_conn_to_VNF>","General server listening...")
    INIT_sock.listen(128)

    while True:
        conn, addr = INIT_sock.accept()
        VNF_sockets.append(0)
        VNF_sockets[nxt_VNF_local_id]=[conn, addr]
        print "[INIT] VNF ({}) : LOCALY REGISTERED <=> VNF_port = {}".format(nxt_VNF_local_id, addr[1])
        mid_log("[INIT] <init_conn_to_VNF>","VNF({}):LOCALY REGISTERED <=> VNF_port = {}".format(nxt_VNF_local_id, addr[1]))
        thr_VNF_sock_recv.append(0)
        thr_VNF_sock_send.append(0)
        thr_VNF_sock_data_cleaner_handlr.append(0)
        VNF_local_global_id.append(0)
        VNF_sock_input_queues.append([])
        VNF_sock_output_queues.append([])

        ## BUILDING AND STARTING 2 LIGHT THREADS FOR SEND AND RECEIVE ON THE VNF SOCKET
        ## BUILDING THE MAIN THREAD DOING DATA CLEANING AND DISTRIBUTING (IF NEEDED) THE DATA RECEIVED FROM THE VNF SOCKET
        thr_VNF_sock_recv[nxt_VNF_local_id]=threading.Thread(target=VNF_sock_recv, args=[nxt_VNF_local_id])
        thr_VNF_sock_data_cleaner_handlr[nxt_VNF_local_id]=threading.Thread(target=VNF_sock_data_cleaner_handlr, args=[nxt_VNF_local_id])
        thr_VNF_sock_send[nxt_VNF_local_id]=threading.Thread(target=VNF_sock_send, args=[nxt_VNF_local_id])
        thr_VNF_sock_recv[nxt_VNF_local_id].start()
        thr_VNF_sock_data_cleaner_handlr[nxt_VNF_local_id].start()
        thr_VNF_sock_send[nxt_VNF_local_id].start()
        nxt_VNF_local_id += 1

def VNF_sock_recv(VNF_ID): # receiver function for the VNF sockets
    global VNF_sock_output_queues, VNF_sockets

    print "[INFO] <VNF_sock_recv> for VNF({}) :[STARTED]".format(VNF_ID)
    mid_log("[INFO] <VNF_sock_recv>", "               for VNF({}) :[STARTED]".format(VNF_ID))
    while True:
        try:
            raw_VNF_received = VNF_sockets[VNF_ID][0].recv(8192)
            VNF_sock_output_queues[VNF_ID].append(raw_VNF_received)
        except:
            raise

def VNF_sock_send(VNF_ID): # sender function for the VNF sockets
    global VNF_sock_input_queues, VNF_sockets

    print "[INFO] <VNF_sock_send>                for VNF({}) :[STARTED]".format(VNF_ID)
    mid_log("[INFO] <VNF_sock_send>", "               for VNF({}) :[STARTED]".format(VNF_ID))
    while True:
        try:
            out_msg = VNF_sock_input_queues[VNF_ID].pop(0)
            print "[VNF][OUT]  <VNF_sock_send>     => msg to VNF ({}), len ({}), kind: ({})".format(VNF_ID,su("H",out_msg[:2])[0],su("H",out_msg[2:4])[0])
            mid_log("[VNF][OUT]  <VNF_sock_send>", "msg to VNF ({},{}), len ({}), kind: ({})".format(VNF_ID,su("H",out_msg[4:6])[0],su("H",out_msg[:2])[0],su("H",out_msg[2:4])[0]))
            VNF_sockets[VNF_ID][0].send(out_msg)
        except IndexError:
            time.sleep(1)
            pass
        except:
            raise

def VNF_sock_data_cleaner_handlr(VNF_ID): # rebuild the msgs coming from the VNF and send to needed queues in the Middle_Ware
    global VNF_sock_input_queues, VNF_sock_output_queues, VNF_subscriptions
    global VNF_publishes, OUT_2_queue,VNF_local_global_id

    current_data = "" # empty for started
    print "[INFO] <VNF_sock_data_cleaner_handlr> for VNF({}) :[STARTED]".format(VNF_ID)
    mid_log("[INFO] <VNF_sock_data_cleaner_handlr>", "for VNF({}) :[STARTED]".format(VNF_ID) )
    while True:
        try:
            # pop the first received chunk and add to the remained bytes (if any)
            current_data = current_data + VNF_sock_output_queues[VNF_ID].pop(0)

            # more than 2 bytes to know the lenght of the msg and enough bytes to rebuild a msg
            while (len(current_data)>2 and len(current_data)>=int(su("H",current_data[:2])[0])):
                in_msg = current_data[:int(su("H",current_data[:2])[0])] # we extract the msg from Data_length(2B)
                mid_log("[MW][IN]  <VNF_sock_data_cleaner_handlr>", "MSG len({}), kind({})".format(su("H",in_msg[:2])[0],
                        su("H",in_msg[2:4])[0]))
                print "[MW][IN] <VNF_sock_data_cleaner_handlr>  => len({}), kind({})".format(su("H",in_msg[:2])[0],
                        su("H",in_msg[2:4])[0])

                #### INITIALIZING VNF_ID REQUEST
                #### => (kind = 0)
                if int(su("H",in_msg[2:4])[0]) == 0: # it is an initializing request from the VNF => send to the SDN controller
                    try:
                        ## msg = Data_length(2B)+Kind(2B)+local_ID(2B)+Global_ID(2B)+VNF_NAME(nB)
                        in_msg_tmp = in_msg[2:4]+sp("H",VNF_ID)+in_msg[6:]
                        in_msg_tmp = sp("H",len(in_msg_tmp)+2)+in_msg_tmp
                        OUT_1_queue.append(in_msg_tmp)

                        #### CUT PROCESSED MSG FROM current_data
                        current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg
                    except:
                        raise

                #### PUB_ID, SUB_ID or RECOVER REQUEST
                #### => (kind = 1, 5 and 6)
                elif int(su("H",in_msg[2:4])[0]) in [1,5,6]: # it is an initializing request from the VNF => send to the SDN controller
                    try:
                        ## msg = Data_length(2B)+Kind(2B)+Global_ID(2B)+VNF_NAME(nB)
                        OUT_1_queue.append(in_msg)

                        #### CUT THE PROCESSED MSG FROM current_data
                        current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg
                    except:
                        raise

                #### PUBLISH
                #### => (kind = 2)
                elif int(su("H",in_msg[2:4])[0]) == 2: # it is a publish msg from VNF
                    try:
                        tmp_var_ID = int(su("H", in_msg[6:8])[0]) # extracting the Variable_ID

                        ## append var_ID to the published list of the related VNF socket
                        if tmp_var_ID in VNF_subscriptions.keys(): # if there is internal subscriptions on this Variable_ID
                            for dest in VNF_subscriptions[tmp_var_ID]:
                                ## msg = Data_length(2B)+Kind(2B)+Local_ID(2B)+Global_ID(4B)+tot_var(2B)
                                msg_copy = copy.deepcopy(in_msg)
                                VNF_sock_input_queues[VNF_local_global_id.index(dest)].append(msg_copy)
                        OUT_2_queue.append(in_msg)

                        #### CUT THE PROCESSED MSG FROM current_data
                        current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg
                    except:
                        raise

                #### SUBSCRIBE REGISTER
                #### => (kind = 3)
                elif int(su("H",in_msg[2:4])[0]) == 3: # it is a subscribe-register request
                    if int(su("H",in_msg[6:8])[0]) not in VNF_subscriptions.keys(): # If variable_ID is NOT in VNF_subscription as a key e.g. var_id:[.....] NOT exists
                        VNF_subscriptions[int(su("H",in_msg[6:8])[0])]=[int(su("H",in_msg[4:6])[0])] # add VNF_GLOBAL_ID to subscriptions of var_id:[]
                        internal_publish = 0
                        print "[INFO] <VNF_sock_data_cleaner_handlr> check before subscribe in SW"
                        print "VNF_publishes: ", VNF_publishes
                        print "VNF_subscriptions: ", VNF_subscriptions
                        for VNF in VNF_publishes.keys():
                            # check internal registered publishes for the var_id
                            if int(su("H",in_msg[6:8])[0]) in VNF_publishes[VNF]:
                                internal_publish = 1
                                break
                        if not internal_publish: # if no internal publish on that var_id exist
                            OUT_2_queue.append(in_msg) # try to send request to the switch
                    else: # If variable_ID is in VNF_subscription as a key
                        if int(su("H",in_msg[4:6])[0]) not in VNF_subscriptions[int(su("H",in_msg[6:8])[0])]: # if VNF_ID is not in the var_id:[]
                            VNF_subscriptions[int(su("H",in_msg[6:8])[0])].append(int(su("H",in_msg[4:6])[0])) # add VNF_ID to subscriptions of var_id

                    #### CUT THE PROCESSED MSG FROM current_data
                    current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg

                #### SUBSCRIBE REMOVE
                #### => (KIND = 4)
                elif int(su("H",in_msg[2:4])[0]) == 4: # it is a subscribe-remove request
                    if (int(su("H",in_msg[6:8])[0]) in VNF_subscriptions.keys() and int(su("H",in_msg[4:6])[0]) in VNF_subscriptions[int(su("H",in_msg[6:8])[0])]):
                        VNF_subscriptions[int(su("H",in_msg[6:8])[0])].remove(int(su("H",in_msg[4:6])[0]))
                    if not VNF_subscriptions[int(su("H",in_msg[6:8])[0])]:
                        internal_publish = 0
                        for VNF in VNF_publishes.keys():
                            if VNF_subscriptions[int(su("H",in_msg[6:8])[0])] in VNF_publishes[VNF]:
                                internal_publish = 1
                                break
                        if not internal_publish:
                            OUT_2_queue.append(in_msg)
                    #### CUT THE PROCESSED MSG FROM current_data
                    current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg

                else:
                    print "WHY? ;)"
        except IndexError:
            time.sleep(1)
            pass
        except:
            raise


########################
###### EXT MODULE ######
########################

'''### REPLICA <==> MW (signaling)###'''
def receive_SIG_msg():
    global IN_1_queue, REPLICA_sock

    my_src = ifaddresses(get_if())[2][0]['addr']
    my_server_name = "H" + str(int(my_src[-1:]))

    print "*********** START ****************"
    print "HOST name : {}".format(my_server_name)
    print "Middle_Ware STARTED"
    print "**********************************"

    REPLICA_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    REPLICA_sock.connect(('10.0.4.4', 65430))
    mid_log("[INIT] <receive_msg>", "Socket   :[MADE]")
    mid_log("[INIT] <receive_msg>", ":[STARTED]")
    print "[INIT] <receive_msg>", "Socket  :[MADE]"
    print "[INIT] <receive_msg>", "        :[STARTED]"
    time.sleep(1)
    while True:
        raw_received = REPLICA_sock.recv(1024)
        IN_1_queue.append(raw_received)

def send_SIG_msg():
    global OUT_1_queue, REPLICA_sock

    mid_log("[INIT] <send_SIG_msg>", "    :[STARTED]")
    print "[INIT] <send_SIG_msg>", "           :[STARTED]"
    while True:
        try:
            out_msg = OUT_1_queue.pop(0)
            mid_log("[OUT] <send_msg>", "MSG len({}), kind({})".format(su("H",out_msg[:2])[0],msg_kind(int(su("H",out_msg[2:4])[0]))))
            print "[OUT] <send_msg> => sending msg with len({}), kind({})".format(su("H",out_msg[:2])[0],msg_kind(int(su("H",out_msg[2:4])[0])))
            if len(out_msg)==int(su("H",out_msg[:2])[0]):
                REPLICA_sock.send(out_msg)
            else:
                print "len(out_msg) != int(su('h',out_msg[:2])[0])"
        except IndexError:
            time.sleep(1)
            pass
        except:
            raise

def sig_msg_hndlr_REPLICA():
    global IN_1_queue

    current_data = "" # empty for started
    mid_log("[INIT] <REPLICA_msg_cleaner_handler>",":[STARTED]")
    print "[INIT] <REPLICA_msg_cleaner_handler> :[STARTED]"
 
    while True:
        try:
            # pop the first received chunk and add to the remained bytes (if any)
            current_data += IN_1_queue.pop(0)

            # more than 2 bytes to know the lenght of the msg and enough bytes to rebuild a msg
            while (len(current_data)>2 and len(current_data)>=int(su("H",current_data[:2])[0])):
                
                # we extract the msg from Data_length(2B)
                in_msg = current_data[:int(su("H",current_data[:2])[0])]

                ### INIT VNF_ID REPLY
                #### => (kind = 0)
                if int(su("H",in_msg[2:4])[0]) == 0: # it is an initializing response from the REPLICA controller => send to the VNF INT module
                    try:
                        mid_log("[INFO] <sig_msg_hndlr_REPLICA>", "INIT VNF_ID REPLY:len({}), kind({}), l_ID({}), G_id({})"\
                                .format(int(su("H", in_msg[:2])[0]),int(su("H", in_msg[2:4])[0]),int(su("H", in_msg[4:6])[0]),int(su("H", in_msg[6:8])[0])))

                        print "[INFO] <sig_msg_hndlr_REPLICA> "
                        print "INIT VNF_ID REPLY: len({}), kind({}), l_ID({}), G_id({})".format(int(su("H", in_msg[:2])[0]),
                               int(su("H", in_msg[2:4])[0]), int(su("H", in_msg[4:6])[0]),int(su("H", in_msg[6:8])[0]))

                        VNF_local_global_id[int(su("H", in_msg[4:6])[0])] = int(su("H", in_msg[6:8])[0]) # update the mapping of Local_ID : Global_ID
                        
                        print "[INFO] <sig_msg_hndlr_REPLICA> VNF_local_global_id: {} ".format(VNF_local_global_id)

                        ## append msg to the input queue of the related VNF socket
                        VNF_sock_input_queues[int(su("H", in_msg[4:6])[0])].append(in_msg)

                        #### CUT PROCESSED MSG FROM current_data
                        current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg
                    except:
                        raise

                ### INIT PUB_ID REPLY
                #### => (kind = 1)
                elif int(su("H",in_msg[2:4])[0]) == 1: # it is a PUB_ID reply from the REPLICA controller => send to the send to the VNF INT module
                    try:
                        mid_log("[INFO] <recv_data_middleware>", "INIT PUB_ID REPLY:len({}), kind({}), G_id({})"\
                                .format(int(su("H", in_msg[:2])[0]),int(su("H", in_msg[2:4])[0]),int(su("H", in_msg[4:6])[0])))

                        print "[INFO] <recv_data_middleware> "
                        print "INIT PUB_ID REPLY: len({}), kind({}), G_id({})".format(int(su("H", in_msg[:2])[0]),
                               int(su("H", in_msg[2:4])[0]), int(su("H", in_msg[4:6])[0]))

                        tmp_var_ID = int(su("H", in_msg[6:8])[0]) # extracting the Variable_ID
                        ## append var_ID to the published list of the related VNF socket
                        if int(su("H", in_msg[4:6])[0]) in VNF_publishes.keys():
                            VNF_publishes[int(su("H", in_msg[4:6])[0])].append(tmp_var_ID)
                        else:
                            VNF_publishes[int(su("H", in_msg[4:6])[0])] = [tmp_var_ID]
                        print "[INFO] <recv_data_middleware> check the VNF_publishes: ", VNF_publishes
                        print "INIT PUB_ID REPLY: len({}), kind({}), G_id({})".format(int(su("H", in_msg[:2])[0]),
                               int(su("H", in_msg[2:4])[0]), int(su("H", in_msg[4:6])[0]))

                        ## append msg to the input queue of the related VNF socket
                        VNF_sock_input_queues[VNF_local_global_id.index(int(su("H", in_msg[4:6])[0]))].append(in_msg)

                        #### CUT PROCESSED MSG FROM current_data
                        current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg
                    except:
                        raise

                ### INIT SUB_ID REPLY
                #### => (kind = 5)
                elif int(su("H",in_msg[2:4])[0]) == 5: # it is a SUB_ID reply from the REPLICA controller => send to the send to the VNF INT module
                    try:
                        mid_log("[INFO]    <recv_data_middleware>", "VARIABLE_ID_REPLY:len({}), kind({}), G_id({}), Var_ID({})"\
                        .format(int(su("H", in_msg[:2])[0]),int(su("H", in_msg[2:4])[0]), int(su("H", in_msg[4:6])[0]),int(su("H", in_msg[6:8])[0])))

                        print "[INFO] <recv_data_middleware>"
                        print "VARIABLE_ID_REPLY: len({}), kind({}), G_id({}), v_ID({})".format(int(su("H", in_msg[:2])[0]),
                               int(su("H", in_msg[2:4])[0]), int(su("H", in_msg[4:6])[0]),int(su("H", in_msg[6:8])[0]))

                        ## append msg to the input queue of the related VNF socket
                        VNF_sock_input_queues[VNF_local_global_id.index(int(su("H", in_msg[4:6])[0]))].append(in_msg)

                        #### CUT PROCESSED MSG FROM current_data
                        current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg
                    except:
                        raise

        except IndexError:
            time.sleep(1)
            pass


'''### MW <==> OUTSIDE (STARE publish/subscribe)###'''
def pub_mcast_membership_maker(group_num):
    global rcv_mw_socks, VNF_sock_input_queues, VNF_subscriptions, VNF_local_global_id

    print "[MW] <pub_mcast_membership>                for var_ID({}) :[STARTED]".format(variable_id)
    mid_log("[MW] <pub_mcast_membership>", "               for var_ID({}) :[STARTED]".format(variable_id))

    # Create the socket
    rcv_mw_socks[group_num] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rcv_mw_socks[group_num].setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

    # Bind to the server address
    rcv_mw_socks[group_num].bind(('', 65432))

def send_data_middleware():# sending packets to network
    global OUT_2_queue, thr_rcv_pub_multi, rcv_mw_socks, all_mcast_groups, mcast_groups, system_default_max

    # Create the datagram socket
    send_mw_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    ## Set the time-to-live for messages
    ttl = struct.pack('b', 2)
    send_mw_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
    group_num = 0
    mcast_groups[group_num]=[]
    while True:
        try:
            out_msg = OUT_2_queue.pop(0)
            mid_log("[SW][OUT] <send_data_middleware>", "MSG len({}), kind({})".format(su("H",out_msg[:2])[0],su("H",out_msg[2:4])[0]))
            print "[SW][OUT] <send_data_middleware>        => len({}), kind({})".format(su("H",out_msg[:2])[0], su("H",out_msg[2:4])[0])

            kind = int(su("H", out_msg[2:4])[0])

            # SUB_register
            if kind==3:
                var_id = int(su("H",out_msg[6:8])[0])
                # Building the multicast group related to the variable_id
                mcast_group = pubSubIP(var_id,2)

                # Tell the operating system to add the socket to the multicast group
                # on all interfaces.
                group = socket.inet_aton(mcast_group)
                mreq = struct.pack('4sL', group, socket.INADDR_ANY)
                all_mcast_groups.append(mcast_group)

                try:
                    rcv_mw_socks[group_num].setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                except:
                    group_num += 1
                    mcast_groups[group_num]=[]
                    ## building a new thread responcible for making a new socket for that var_id,
                    ## but not receiving, just letting us do more IP_multicast_membersip
                    rcv_mw_socks[group_num]=threading.Thread(target=pub_mcast_membership_maker, args=[group_num])
                    print "[INFO] send_data_middleware: buiding...", rcv_mw_socks
                    rcv_mw_socks[group_num].start()
                    print "[INFO] send_data_middleware: starting...", rcv_mw_socks
                    with open("error_mreq_report.txt","a") as f:
                        f.write("handled membership error due to OS limit,receiver thread for: %s ,group: %s\n" % (str(var_id),mcast_group))
                    pass
                
                mcast_groups[group_num].append(mcast_group)

            elif kind in [2,4,6]: # publish, sub_remove, recover
                var_id = int(su("H",out_msg[6:8])[0])
            elif kind in [0,1,5]: # init_VNF, pub_variable_id_request, sub_variable_id_request
                var_id = 0

            ## making proper destination and sending the msg
            dest_addr = (pubSubIP(var_id, kind),65432)
            sent = send_mw_sock.sendto(out_msg, dest_addr)

        except IndexError:
            time.sleep(1)
            pass

def recv_data_middleware():
    global VNF_local_global_id, VNF_local_global_id, VNF_publishes, VNF_sock_input_queues, rcv_mw_sock
    global VNF_subscriptions, rcv_mw_socks
   
    # Create the socket
    rcv_mw_socks[0] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rcv_mw_socks[0].setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

    # Bind to the server address
    rcv_mw_socks[0].bind(('', 65432))
    while True:

        data, addr_uni = rcv_mw_socks[0].recvfrom(2048)
        try:
            mid_log("[SW][IN]  <recv_data_middleware>", "MSG len({}), kind({})".format(su("H",data[:2])[0],
                    su("H",data[2:4])[0]))
            print "[SW][IN] <recv_data_middleware>      => len({}), kind({})".format(su("H",data[:2])[0],
                    su("H",data[2:4])[0])
        except:
            pass

         ### PUBLISH
        if int(su("H", data[2:4])[0])==2:
            mid_log("[SW][IN]  <rcv_mw_sock({})>".format(str(int(su("H", data[6:8])[0]))), "PUBLISH packet")
            if int(su("H",data[6:8])[0]) in VNF_subscriptions.keys(): # if there is internal subscriptions on this Variable_ID
                for dest in VNF_subscriptions[int(su("H",data[6:8])[0])]:

                    print "[INFO] <rcv_mw_sock({})>".format(str(int(su("H", data[6:8])[0])))
                    print "PUBLISH : len({}), kind({}), G_id({})".format(int(su("H", data[:2])[0]),
                           int(su("H", data[2:4])[0]), int(su("H", data[4:6])[0]))
                    ## msg = Data_length(2B)+Kind(2B)+Global_ID(4B)+tot_var(2B)
                    msg_copy = copy.deepcopy(data)
                    VNF_sock_input_queues[VNF_local_global_id.index(dest)].append(msg_copy)

def main():

    thr_RECEIVE_SIG_MW = threading.Thread(target = receive_SIG_msg)
    thr_MAIN_MESSAGE_HANDLER_MW = threading.Thread(target = sig_msg_hndlr_REPLICA)
    thr_SEND_SIG_MW = threading.Thread(target = send_SIG_msg)
    thr_INIT_VNFs = threading.Thread(target = init_conn_to_VNF)
    thr_MAIN_SEND = threading.Thread(target = send_data_middleware)
    thr_MAIN_RECEIVE = threading.Thread(target = recv_data_middleware)

    thr_RECEIVE_SIG_MW.start()
    time.sleep(1)

    thr_MAIN_MESSAGE_HANDLER_MW.start()
    time.sleep(1)

    thr_SEND_SIG_MW.start()
    time.sleep(1)

    thr_INIT_VNFs.start()
    time.sleep(1)

    thr_MAIN_SEND.start()
    time.sleep(1)

    thr_MAIN_RECEIVE.start()

    thr_RECEIVE_SIG_MW.join()
    thr_MAIN_MESSAGE_HANDLER_MW.join()
    thr_SEND_SIG_MW.join()
    thr_INIT_VNFs.join()
    thr_MAIN_SEND.join()
    thr_MAIN_RECEIVE.join()


if __name__ == '__main__':
    main()
