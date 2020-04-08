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
nxt_NF_local_id = 1
rcv_mw_socks = [0]
# system_default_max = 20

NF_sockets = [0] #  NF_LOCAL_ID = Index of the [socket object of the correspondent NF , (address, port)]
NF_local_global_id = [0] # NF_LOCAL_ID = Index of the NF_GLOBAL_ID
rcv_mw_sock_multi = {} # var_id: socket object for listenig on the multicast server socket,regarding to that var_id
all_mcast_groups = []
mcast_groups = [0]

thr_NF_sock_recv = [0] # NF_LOCAL_ID = Index of the thread receiving on sockets connected to the NFs
thr_NF_sock_send = [0] # NF_LOCAL_ID = Index of the threads sending on sockets connected to the NFs
thr_NF_sock_data_cleaner_handlr = [0] # NF_LOCAL_ID = Index of the thread cleaning and handling msg received from NFs
thr_rcv_pub_multi = {} # var_id: thread object for listenig on the multicast server socket,regarding to that var_id

NF_subscriptions = {} # subscribed variable_IDs : [subscribed NF_GLOBAL_ID]
NF_publishes = {} # NF_GLOBAL_ID : [publishing variable_IDs]

NF_sock_input_queues = [0] # NF_LOCAL_ID = Index of the queue for NF_sock_send
NF_sock_output_queues = [0] # NF_LOCAL_ID = Index of the queue for NF_sock_recv

received_data_internal = [] # my queue for msgs from the inside of the server


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
    if kind in [0,1,5,6]:# "INIT_NF_ID","INIT_PUB_ID", "Variable_ID_REQ", "RECOVER"
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


'''### NF <==> MW ###'''
def init_conn_to_nf(): # Initializing  the Middle_Ware, making general server listening for NF connections
    global my_server_name, nxt_NF_local_id, NF_local_global_id, NF_sockets
    global thr_NF_sock_recv, thr_NF_sock_send, thr_NF_sock_data_cleaner_handlr

    my_src = ifaddresses(get_if())[2][0]['addr']
    my_server_name = "H" + str(int(my_src[-1:]))

    print "*********** START ****************"
    print "HOST name : {}".format(my_server_name)
    print "Middle_Ware STARTED"
    print "**********************************"

    mid_log("[INIT] <init_conn_to_nf>", "HOST name: {}, Middle_Ware :[STARTED]".format(my_server_name))
    general_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    general_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    general_sock.bind(("localhost",65431))
    print "[INIT] General server listening...\n"
    mid_log("[INIT] <init_conn_to_nf>","General server listening...")
    general_sock.listen(128)

    while True:
        conn, addr = general_sock.accept()
        NF_sockets.append(0)
        NF_sockets[nxt_NF_local_id]=[conn, addr]
        print "[INIT] NF ({}) : LOCALY REGISTERED <=> NF_port = {}\n".format(nxt_NF_local_id, addr[1])
        mid_log("[INIT] <init_conn_to_nf>","NF({}):LOCALY REGISTERED <=> NF_port = {}\n".format(nxt_NF_local_id, addr[1]))
        thr_NF_sock_recv.append(0)
        thr_NF_sock_send.append(0)
        thr_NF_sock_data_cleaner_handlr.append(0)
        NF_local_global_id.append(0)
        NF_sock_input_queues.append([])
        NF_sock_output_queues.append([])

        ## BUILDING AND STARTING 2 LIGHT THREADS FOR SEND AND RECEIVE ON THE NF SOCKET
        ## BUILDING THE MAIN THREAD DOING DATA CLEANING AND DISTRIBUTING (IF NEEDED) THE DATA RECEIVED FROM THE NF SOCKET
        thr_NF_sock_recv[nxt_NF_local_id]=threading.Thread(target=NF_sock_recv, args=[nxt_NF_local_id])
        thr_NF_sock_data_cleaner_handlr[nxt_NF_local_id]=threading.Thread(target=NF_sock_data_cleaner_handlr, args=[nxt_NF_local_id])
        thr_NF_sock_send[nxt_NF_local_id]=threading.Thread(target=NF_sock_send, args=[nxt_NF_local_id])
        thr_NF_sock_recv[nxt_NF_local_id].start()
        thr_NF_sock_data_cleaner_handlr[nxt_NF_local_id].start()
        thr_NF_sock_send[nxt_NF_local_id].start()
        nxt_NF_local_id += 1

def NF_sock_recv(NF_ID): # receiver function for the NF sockets
    global NF_sock_output_queues, NF_sockets

    print "\n[INFO] <NF_sock_recv> for NF({}) :[STARTED]".format(NF_ID)
    mid_log("[INFO] <NF_sock_recv>", "               for NF({}) :[STARTED]".format(NF_ID))
    while True:
        try:
            raw_NF_received = NF_sockets[NF_ID][0].recv(8192)
            NF_sock_output_queues[NF_ID].append(raw_NF_received)
        except:
            raise

def NF_sock_send(NF_ID): # sender function for the NF sockets
    global NF_sock_input_queues, NF_sockets

    print "\n[INFO] <NF_sock_send>                for NF({}) :[STARTED]\n".format(NF_ID)
    mid_log("[INFO] <NF_sock_send>", "               for NF({}) :[STARTED]\n".format(NF_ID))
    while True:
        try:
            out_msg = NF_sock_input_queues[NF_ID].pop(0)
            print "[NF][OUT]  <NF_sock_send>     => msg to NF ({}), len ({}), kind: ({})".format(NF_ID,su("H",out_msg[:2])[0],su("H",out_msg[2:4])[0])
            mid_log("[NF][OUT]  <NF_sock_send>", "msg to NF ({},{}), len ({}), kind: ({})".format(NF_ID,su("H",out_msg[4:6])[0],su("H",out_msg[:2])[0],su("H",out_msg[2:4])[0]))
            NF_sockets[NF_ID][0].send(out_msg)
        except IndexError:
            time.sleep(1)
            pass
        except:
            raise

def NF_sock_data_cleaner_handlr(NF_ID): # rebuild the msgs coming from the NF and send to needed queues in the Middle_Ware
    global NF_sock_input_queues, NF_sock_output_queues, NF_subscriptions
    global NF_publishes, received_data_internal,NF_local_global_id

    current_data = "" # empty for started
    print "\n[INFO] <NF_sock_data_cleaner_handlr> for NF({}) :[STARTED]".format(NF_ID)
    mid_log("[INFO] <NF_sock_data_cleaner_handlr>", "for NF({}) :[STARTED]".format(NF_ID) )
    while True:
        try:
            # pop the first received chunk and add to the remained bytes (if any)
            current_data = current_data + NF_sock_output_queues[NF_ID].pop(0)

            # more than 2 bytes to know the lenght of the msg and enough bytes to rebuild a msg
            while (len(current_data)>2 and len(current_data)>=int(su("H",current_data[:2])[0])):
                in_msg = current_data[:int(su("H",current_data[:2])[0])] # we extract the msg from Data_length(2B)
                mid_log("[MW][IN]  <NF_sock_data_cleaner_handlr>", "MSG len({}), kind({})".format(su("H",in_msg[:2])[0],
                        su("H",in_msg[2:4])[0]))
                print "[MW][IN] <NF_sock_data_cleaner_handlr>  => len({}), kind({})".format(su("H",in_msg[:2])[0],
                        su("H",in_msg[2:4])[0])

                #### INITIALIZING NF_ID REQUEST
                #### => (kind = 0)
                if int(su("H",in_msg[2:4])[0]) == 0: # it is an initializing request from the NF => send to the SDN controller
                    ## msg = Data_length(2B)+Kind(2B)+local_ID(2B)+Global_ID(2B)+NF_NAME(nB)
                    in_msg_tmp = in_msg[2:4]+sp("H",NF_ID)+in_msg[6:]
                    in_msg_tmp = sp("H",len(in_msg_tmp)+2)+in_msg_tmp
                    received_data_internal.append(in_msg_tmp)

                    #### CUT PROCESSED MSG FROM current_data
                    current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg

                #### PUB_ID, SUB_ID or RECOVER REQUEST
                #### => (kind = 1, 5 and 6)
                elif int(su("H",in_msg[2:4])[0]) in [1,5,6]: # it is an initializing request from the NF => send to the SDN controller
                    ## msg = Data_length(2B)+Kind(2B)+Global_ID(2B)+NF_NAME(nB)
                    received_data_internal.append(in_msg)

                    #### CUT THE PROCESSED MSG FROM current_data
                    current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg

                #### PUBLISH
                #### => (kind = 2)
                elif int(su("H",in_msg[2:4])[0]) == 2: # it is a publish msg from NF
                    tmp_var_ID = int(su("H", in_msg[6:8])[0]) # extracting the Variable_ID

                    ## append var_ID to the published list of the related NF socket
                    if tmp_var_ID in NF_subscriptions.keys(): # if there is internal subscriptions on this Variable_ID
                        for dest in NF_subscriptions[tmp_var_ID]:
                            ## msg = Data_length(2B)+Kind(2B)+Local_ID(2B)+Global_ID(4B)+tot_var(2B)
                            msg_copy = copy.deepcopy(in_msg)
                            NF_sock_input_queues[NF_local_global_id.index(dest)].append(msg_copy)
                    received_data_internal.append(in_msg)

                    #### CUT THE PROCESSED MSG FROM current_data
                    current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg

                #### SUBSCRIBE REGISTER
                #### => (kind = 3)
                elif int(su("H",in_msg[2:4])[0]) == 3: # it is a subscribe-register request
                    if int(su("H",in_msg[6:8])[0]) not in NF_subscriptions.keys(): # If variable_ID is NOT in NF_subscription as a key e.g. var_id:[.....] NOT exists
                        NF_subscriptions[int(su("H",in_msg[6:8])[0])]=[int(su("H",in_msg[4:6])[0])] # add NF_GLOBAL_ID to subscriptions of var_id:[]
                        internal_publish = 0
                        print "\n[INFO] <NF_sock_data_cleaner_handlr> check before subscribe in SW"
                        print "NF_publishes: ", NF_publishes
                        print "NF_subscriptions: ", NF_subscriptions
                        for nf in NF_publishes.keys():
                            # check internal registered publishes for the var_id
                            if int(su("H",in_msg[6:8])[0]) in NF_publishes[nf]:
                                internal_publish = 1
                                break
                        if not internal_publish: # if no internal publish on that var_id exist
                            received_data_internal.append(in_msg) # try to send request to the switch
                    else: # If variable_ID is in NF_subscription as a key
                        if int(su("H",in_msg[4:6])[0]) not in NF_subscriptions[int(su("H",in_msg[6:8])[0])]: # if NF_ID is not in the var_id:[]
                            NF_subscriptions[int(su("H",in_msg[6:8])[0])].append(int(su("H",in_msg[4:6])[0])) # add NF_ID to subscriptions of var_id

                    #### CUT THE PROCESSED MSG FROM current_data
                    current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg

                #### SUBSCRIBE REMOVE
                #### => (KIND = 4)
                elif int(su("H",in_msg[2:4])[0]) == 4: # it is a subscribe-remove request
                    if (int(su("H",in_msg[6:8])[0]) in NF_subscriptions.keys() and int(su("H",in_msg[4:6])[0]) in NF_subscriptions[int(su("H",in_msg[6:8])[0])]):
                        NF_subscriptions[int(su("H",in_msg[6:8])[0])].remove(int(su("H",in_msg[4:6])[0]))
                    if not NF_subscriptions[int(su("H",in_msg[6:8])[0])]:
                        internal_publish = 0
                        for nf in NF_publishes.keys():
                            if NF_subscriptions[int(su("H",in_msg[6:8])[0])] in NF_publishes[nf]:
                                internal_publish = 1
                                break
                        if not internal_publish:
                            received_data_internal.append(in_msg)
                    #### CUT THE PROCESSED MSG FROM current_data
                    current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg

                else:
                    print "WHY? ;)"
        except IndexError:
            time.sleep(1)
            pass
        except:
            raise


'''### MW <==> OUTSIDE ###'''
def pub_mcast_membership_thr(group_num):
    global rcv_mw_socks, NF_sock_input_queues, NF_subscriptions, NF_local_global_id

    print "[MW] <pub_mcast_membership>                for var_ID({}) :[STARTED]\n".format(variable_id)
    mid_log("[MW] <pub_mcast_membership>", "               for var_ID({}) :[STARTED]\n".format(variable_id))

    # Create the socket
    rcv_mw_socks[group_num] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rcv_mw_socks[group_num].setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

    # Bind to the server address
    rcv_mw_socks[group_num].bind(('', 65432))

def send_data_middleware():# sending packets to network
    global received_data_internal, thr_rcv_pub_multi, rcv_mw_socks, all_mcast_groups, mcast_groups, system_default_max

    # Create the datagram socket
    send_mw_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    ## Set the time-to-live for the messages
    ttl = struct.pack('b', 2)
    send_mw_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
    group_num = 0
    mcast_groups[group_num]=[]
    while True:
        try:
            out_msg = received_data_internal.pop(0)
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
                    ## building a new thread responsible for making a new socket for that var_id,
                    ## but not receiving, just letting us do more IP_multicast_membersip
                    rcv_mw_socks[group_num]=threading.Thread(target=pub_mcast_membership_thr, args=[group_num])
                    print "\n[INFO] send_data_middleware: buiding...\n", rcv_mw_socks
                    rcv_mw_socks[group_num].start()
                    print "\n[INFO] send_data_middleware: starting...\n", rcv_mw_socks
                    with open("error_mreq_report.txt","a") as f:
                        f.write("handled membership error due to OS limit,receiver thread for: %s ,group: %s\n" % (str(var_id),mcast_group))
                    pass
                
                mcast_groups[group_num].append(mcast_group)

            elif kind in [2,4,6]: # publish, sub_remove, recover
                var_id = int(su("H",out_msg[6:8])[0])
            elif kind in [0,1,5]: # init_NF, pub_variable_id_request, sub_variable_id_request
                var_id = 0

            ## making proper destination and sending the msg
            dest_addr = (pubSubIP(var_id, kind),65432)
            sent = send_mw_sock.sendto(out_msg, dest_addr)

        except IndexError:
            time.sleep(1)
            pass

def recv_data_middleware():
    global NF_local_global_id, NF_local_global_id, NF_publishes, NF_sock_input_queues, rcv_mw_sock
    global NF_subscriptions, rcv_mw_socks
    # Create the socket
    rcv_mw_socks[0] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rcv_mw_socks[0].setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

    # Bind to the server address
    rcv_mw_socks[0].bind(('', 65432))
    while True:

        data, addr_uni = rcv_mw_socks[0].recvfrom(2048)
        mid_log("[SW][IN]  <recv_data_middleware>", "MSG len({}), kind({})".format(su("H",data[:2])[0],
                su("H",data[2:4])[0]))
        print "[SW][IN] <recv_data_middleware>      => len({}), kind({})".format(su("H",data[:2])[0],
                su("H",data[2:4])[0])
 
        ### INIT NF_ID REPLY
        if int(su("H", data[2:4])[0])==0:
            mid_log("\n[INFO] <recv_data_middleware>", "INIT NF_ID REPLY:len({}), kind({}), l_ID({}), G_id({})\n"\
                    .format(int(su("H", data[:2])[0]),int(su("H", data[2:4])[0]),int(su("H", data[4:6])[0]),int(su("H", data[6:8])[0])))

            print "\n[INFO] <recv_data_middleware> "
            print "INIT NF_ID REPLY: len({}), kind({}), l_ID({}), G_id({})\n".format(int(su("H", data[:2])[0]),
                   int(su("H", data[2:4])[0]), int(su("H", data[4:6])[0]),int(su("H", data[6:8])[0]))

            NF_local_global_id[int(su("H", data[4:6])[0])] = int(su("H", data[6:8])[0]) # update the mapping of Local_ID : Global_ID
            print "\n[INFO] <recv_data_middleware> NF_local_global_id: {} \n".format(NF_local_global_id)
            NF_sock_input_queues[int(su("H", data[4:6])[0])].append(data) ## append msg to the input queue of the related NF socket

        ### INIT PUB_ID REPLY
        elif int(su("H", data[2:4])[0])==1:
            mid_log("\n[INFO] <recv_data_middleware>", "INIT PUB_ID REPLY:len({}), kind({}), G_id({})\n"\
                    .format(int(su("H", data[:2])[0]),int(su("H", data[2:4])[0]),int(su("H", data[4:6])[0])))

            print "\n[INFO] <recv_data_middleware> "
            print "INIT PUB_ID REPLY: len({}), kind({}), G_id({})\n".format(int(su("H", data[:2])[0]),
                   int(su("H", data[2:4])[0]), int(su("H", data[4:6])[0]))

            tmp_var_ID = int(su("H", data[6:8])[0]) # extracting the Variable_ID
            ## append var_ID to the published list of the related NF socket
            if int(su("H", data[4:6])[0]) in NF_publishes.keys():
                NF_publishes[int(su("H", data[4:6])[0])].append(tmp_var_ID)
            else:
                NF_publishes[int(su("H", data[4:6])[0])] = [tmp_var_ID]
            print "\n[INFO] <recv_data_middleware> check the NF_publishes: ",NF_publishes
            print "INIT PUB_ID REPLY: len({}), kind({}), G_id({})\n".format(int(su("H", data[:2])[0]),
                   int(su("H", data[2:4])[0]), int(su("H", data[4:6])[0]))

            ## append msg to the input queue of the related NF socket
            NF_sock_input_queues[NF_local_global_id.index(int(su("H", data[4:6])[0]))].append(data)

        ### PUBLISH
        elif int(su("H", data[2:4])[0])==2:
            mid_log("[SW][IN]  <rcv_mw_sock({})>".format(str(int(su("H", data[6:8])[0]))), "PUBLISH packet")
            if int(su("H",data[6:8])[0]) in NF_subscriptions.keys(): # if there is internal subscriptions on this Variable_ID
                for dest in NF_subscriptions[int(su("H",data[6:8])[0])]:

                    print "\n[INFO] <rcv_mw_sock({})>".format(str(int(su("H", data[6:8])[0])))
                    print "PUBLISH : len({}), kind({}), G_id({})".format(int(su("H", data[:2])[0]),
                           int(su("H", data[2:4])[0]), int(su("H", data[4:6])[0]))
                    ## msg = Data_length(2B)+Kind(2B)+Global_ID(4B)+tot_var(2B)
                    msg_copy = copy.deepcopy(data)
                    NF_sock_input_queues[NF_local_global_id.index(dest)].append(msg_copy)

        ### VARIABLE_ID_REPLY
        elif int(su("H", data[2:4])[0])==5:
            mid_log("\n[INFO]    <recv_data_middleware>", "VARIABLE_ID_REPLY:len({}), kind({}), G_id({}), Var_ID({})\n"\
            .format(int(su("H", data[:2])[0]),int(su("H", data[2:4])[0]), int(su("H", data[4:6])[0]),int(su("H", data[6:8])[0])))

            print "\n[INFO] <recv_data_middleware>"
            print "VARIABLE_ID_REPLY: len({}), kind({}), G_id({}), v_ID({})\n".format(int(su("H", data[:2])[0]),
                   int(su("H", data[2:4])[0]), int(su("H", data[4:6])[0]),int(su("H", data[6:8])[0]))

            ## append msg to the input queue of the related NF socket
            NF_sock_input_queues[NF_local_global_id.index(int(su("H", data[4:6])[0]))].append(data)

def main():

    thr_init = threading.Thread(target = init_conn_to_nf)
    thr_ext_send = threading.Thread(target = send_data_middleware)
    thr_ext_recv = threading.Thread(target = recv_data_middleware)

    thr_init.start()
    thr_ext_send.start()
    thr_ext_recv.start()

    thr_init.join()
    thr_ext_send.join()
    thr_ext_recv.join()


if __name__ == '__main__':
    main()
