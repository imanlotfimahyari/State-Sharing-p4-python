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


import random
import struct
import socket
from struct import pack as sp
from struct import unpack as su
import sys
from datetime import datetime as dt
from netifaces import ifaddresses
from scapy.all import get_if_list

# <<<<<<<< data structures >>>>>>>>>>>>>> #
server_address = ('', 65432)
recv_REPLICA_sock = ""
send_REPLICA_sock = ""
my_name = "---"
nxt_NF_global_id = 5001
nxt_variable_global_id = 1

global_name_NF_id = {}
global_name_variable_id = {}
NF_pub_global_ids = {}

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

def init_REPLICA(): # initializing the host ,NF_ID, pub_topic and Sub_topics(POC)
    global my_name, send_REPLICA_sock, recv_REPLICA_sock, server_address

    my_src = ifaddresses(get_if())[2][0]['addr']
    num = int(my_src[-1:])
    my_name = "<REPLICA Controller> on H" + str(num)
    print "*********** START ****************"
    print "HOST name : {}".format(my_name)
    print "**********************************"
    REPLICA_log("[INIT] <init_REPLICA>"," REPLICA Controller in server H{}:  [STARTED]".format(str(num)))

    # Create the datagram socket
    send_REPLICA_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_REPLICA_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # recv_REPLICA_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR , 1)
    recv_REPLICA_sock.bind(server_address)
    print "REPLICA Controller is listening on requests......"
    REPLICA_log("[[INIT] <init_REPLICA>", "REPLICA Controller is listening on requests......")

def handle_pkt_REPLICA():
    global recv_REPLICA_sock, send_REPLICA_sock
    global nxt_NF_global_id, nxt_variable_global_id
    global NF_pub_global_ids, global_name_NF_id

    while True:
        msg, msg_address = recv_REPLICA_sock.recvfrom(2048)
        try:
            REPLICA_log("\n[SW][IN] <handle_pkt_REPLICA> ", " => len({}), kind({})".format(su("H",msg[:2])[0],msg_kind(int(su("H",msg[2:4])[0]))))
            print "\nGot msg => kind({})".format(msg_kind(int(su("H",msg[2:4])[0])))
            # print "[SW][IN] <handle_pkt_REPLICA> => len({}), kind({})".format(su("H",msg[:2])[0],su("H",msg[2:4])[0])
        except:
            raise

        ### INIT NF_ID MSG
        ### (kind = 0)
        if int(su("H",msg[2:4])[0])==0:
            REPLICA_log("[SW][IN] <handle_pkt_REPLICA> ", "INIT_NF_ID request msg received.")
            print  "INIT_NF_ID REQUEST msg received."
            global_name_NF_id["".join([su("c", x)[0] for x in msg[8:]])] = nxt_NF_global_id # mapping NF_NAME : NF_ID
            NF_pub_global_ids[nxt_NF_global_id] = []
            tmp_msg = msg[2:6]+sp("H",nxt_NF_global_id)+msg[8:]
            tmp_msg = sp("H",len(tmp_msg)+2) + tmp_msg
            try:
                dest_addr = (msg_address[0],65432)
                sent = send_REPLICA_sock.sendto(tmp_msg, dest_addr)
            except:
                raise

            REPLICA_log("[SW][IN] <handle_pkt_REPLICA> ", "INIT_NF_ID reply msg sent.")
            print "INIT_NF_ID REPLY msg sent."
            nxt_NF_global_id += 1

        ### INIT PUB_ID MSG
        ### (kind = 1)
        elif int(su("H",msg[2:4])[0])==1:
            REPLICA_log("[SW][IN] <handle_pkt_REPLICA> ", "INIT_PUB_ID request msg received.")
            print "INIT_PUB_ID request msg received."
            global_name_variable_id["".join([su("c", x)[0] for x in msg[6:]])] = nxt_variable_global_id
            NF_pub_global_ids[int(su("H",msg[4:6])[0])].append(nxt_variable_global_id)
            tmp_msg = msg[2:6]+sp("H",nxt_variable_global_id)+msg[6:]
            tmp_msg = sp("H",len(tmp_msg)+2) + tmp_msg
            try:
                dest_addr = (msg_address[0],65432)
                sent = send_REPLICA_sock.sendto(tmp_msg, dest_addr)
            except:
                raise

            REPLICA_log("[SW][IN] <handle_pkt_REPLICA> ", "INIT_PUB_ID reply msg sent.")
            print "INIT_PUB_ID REPLY msg sent."
            nxt_variable_global_id += 1

        ### VARIABLE_ID request
        ### (kind = 5)
        elif int(su("H",msg[2:4])[0])==5:
            REPLICA_log("[SW][IN] <handle_pkt_REPLICA> ","Variable_ID request msg received.")
            print "Variable_ID request msg received."
            var_name = "".join([su("c", x)[0] for x in msg[6:]])
            if var_name in global_name_variable_id.keys():
                tmp_msg = msg[2:6]+sp("H",global_name_variable_id[var_name])+msg[6:]
                tmp_msg = sp("H",len(tmp_msg)+2) + tmp_msg
                REPLICA_log("[SW][IN] <handle_pkt_REPLICA> ","Variable_ID reply msg sent.")
                print "Variable_ID reply msg sent."
            else:
                tmp_msg = msg[2:6]+sp("H", 0)+msg[6:]
                tmp_msg = sp("H",len(tmp_msg)+2) + tmp_msg
                REPLICA_log("[SW][IN] <handle_pkt_REPLICA> ","Variable_ID reply (ERROR) msg sent.")
                print "Variable_ID reply (ERROR) msg sent."
            try:
                dest_addr = (msg_address[0],65432)
                sent = send_REPLICA_sock.sendto(tmp_msg, dest_addr)
            except:
                raise

        ### RECOVER msg
        ### (kind = 6)
        elif int(su("H",msg[2:4])[0])==6:
            REPLICA_log("[SW][IN] <handle_pkt_REPLICA> ", "RECOVER msg received.")
            print "RECOVER msg : \n"
            print msg

def main():

    init_REPLICA()
    handle_pkt_REPLICA()

if __name__ == '__main__':
    main()
