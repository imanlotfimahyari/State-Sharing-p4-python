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
import time
import random
import struct
from struct import pack as sp
from struct import unpack as su
import argparse
import hashlib
import select
import traceback
import sys
from datetime import datetime as dt
from scapy.all import *

## <<<<<<<< data structures >>>>>>>>>>>>>> ##
NF_names = ["/onem2m/torino_5g/libeliumscanners/wifi/scanner1",
            "/onem2m/torino_5g/libeliumscanners/wifi/scanner2",
            "/onem2m/torino_5g/libeliumscanners/wifi/scanner3",
            "/onem2m/torino_5g/libeliumscanners/wifi/scanner4"]

variable_names = ["logs/wifi/scanner11", "logs/wifi/scanner12", "logs/wifi/scanner13", "logs/wifi/scanner14",
                  "logs/wifi/scanner21", "logs/wifi/scanner22", "logs/wifi/scanner23", "logs/wifi/scanner24",
                  "logs/wifi/scanner31", "logs/wifi/scanner32", "logs/wifi/scanner33", "logs/wifi/scanner34",
                  "logs/wifi/scanner41", "logs/wifi/scanner42", "logs/wifi/scanner43", "logs/wifi/scanner44"]

# mapping for the Variable_names to the variable_global_IDs
var_names_IDs = {"logs/wifi/scanner11":0, "logs/wifi/scanner12":0, "logs/wifi/scanner13":0, "logs/wifi/scanner14":0,
                  "logs/wifi/scanner21":0, "logs/wifi/scanner22":0, "logs/wifi/scanner23":0, "logs/wifi/scanner24":0,
                  "logs/wifi/scanner31":0, "logs/wifi/scanner32":0, "logs/wifi/scanner33":0, "logs/wifi/scanner34":0,
                  "logs/wifi/scanner41":0, "logs/wifi/scanner42":0, "logs/wifi/scanner43":0, "logs/wifi/scanner44":0}

NF_name = "-" # NF_name
NF_id = 0 # Global_ID

variable_name = "-" # Publish variable_name
variable_id = 0 # Global variable_ID

init_NF_ID = 0 # init_NF_ID flag
init_PUB_ID = 0 # init_PUB_ID flag
init_SUB_ID = 0 # init_SUB_ID

answer = 0 # flag of having the SUB_ID_answer from the SDN controller
SUB_ID_ans = "-" # translation of SUB_ID_answer from the SDN controller

NF_sock = 0 # The socket object of the connection between NF and the Middle_Ware
update_num = 0  # Update number for thevariable_ID

sending_queue = [] # msg queue for sending data out of the NFbthrough the TCP socket connected to the Middlle-Ware
received_queue = [] # msg queue for received data from the TCP socket connected to the Middlle-Ware

global_table_last_frame = {} # EXAMPLE => variable_id:[update_num,frag_tot,frag_num] => 12:[1,0,0], ...
drop_update = {} # dorp flags for ("variable_ID, update_num")
tmp_recvd_publishes = {} # temporary holding for publishes of a certain uppdate of a certain variable_id


#### INITIALIZING PART + CONTINUESLY PUBLISH
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

def NF_log(func,the_log): # logging events in file for furthur debbuging
    global NF_id

    fileName = "logs/NF_Gid_"+str(NF_id)+"log.txt"
    with open(fileName,"a") as f:
        data ="["+str(dt.now())+"] "+func+"  "+the_log+"\n"
        f.write(data)

def makeData(variable_id, up_num): # publish maker
    global NF_id

    fileName = "logs/P_NF_Gid_"+str(NF_id) + "_Vid" + str(variable_id)
    new_data_length = 4 # random.randint(10, 50))
    data = ""
    alpha = ["a","b","c","d","e","f","g","h","i","j","k","l","m",
            "n","o","p","q","r","s","t","u","v","w","x","y","z"]
    for i in range(new_data_length):
        rssi = "{RSSI:-" + str(random.randrange(99))
        info = "Vendor:" + "".join(random.sample([alpha[i] for i in range(len(alpha))],
                k=random.randint(5,9))) + " Corporation"
        randomMac = ":".join("%02x"%random.randrange(256) for _ in range(6))
        a = hashlib.new("sha224")
        a.update(randomMac)
        hashedMac = "MAC:"+a.hexdigest().upper()+"}"
        time = "TimeStamp:"+str(dt.now())
        elements = [rssi,info,time,hashedMac,"\n,"]
        line = ",".join(elements)
        data += line
        i += 1

    # open file for external save(DEBUGING)
    with open(fileName,"a") as f:
        f.write("..UPDATE"+str(up_num).zfill(16)+",") # my delimiter for the updates
        f.write(data)
    return data

def publish_updates():
    global NF_id, variable_id, sending_queue, update_num

    while True:
        update_num += 1
        new_data = makeData(variable_id, update_num)
        NF_log("[OUT] <publish_updates>","making update ({}) for variable_id ({})".format(update_num,variable_id))
        msg_len = 1400 # length of pure data each packet should carry
        frag_num = 1    # fragment number
        frag_tot = len(new_data) / msg_len # Total fragments for the update
        if len(new_data) % msg_len != 0:
            frag_tot += 1
        while frag_tot >= frag_num:
            tmp_msg = new_data[msg_len * (frag_num-1) : msg_len * frag_num] # data chunk of length = msg_len

            # msg = length(2B)+kind(2B)+Global_ID(2B)+Variable_id(2B)+update_num(2B)+frag_tot(2B)+frag_num(2B)+pure data(nB)
            pub_msg = sp("HHHHHHH", len(tmp_msg)+14, 2, NF_id, variable_id, update_num, frag_tot, frag_num) + "".join([sp("c", x) for x in tmp_msg])
            NF_log("[OUT] <publish_updates>","adding publish on variable ({}) sending_queue".format(variable_id))
            sending_queue.append(pub_msg)
            frag_num += 1
        time.sleep(20)

def send_msg():
    global sending_queue, NF_sock

    NF_log("[INIT] <send_msg>", "    :[STARTED]")
    print "[INIT] <send_msg>", "           :[STARTED]"
    while True:
        try:
            out_msg = sending_queue.pop(0)
            NF_log("[OUT] <send_msg>", "MSG len({}), kind({})".format(su("H",out_msg[:2])[0],msg_kind(int(su("H",out_msg[2:4])[0]))))
            print "[OUT] <send_msg> => sending msg with len({}), kind({})\n".format(su("H",out_msg[:2])[0],msg_kind(int(su("H",out_msg[2:4])[0])))
            if len(out_msg)==int(su("H",out_msg[:2])[0]):
                NF_sock.send(out_msg)
            else:
                print "len(out_msg) != int(su('h',out_msg[:2])[0])"
        except IndexError:
            time.sleep(1)
            pass
        except:
            raise

def receive_msg():
    global received_queue, NF_sock

    NF_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    NF_sock.connect(("localhost", 65431))
    NF_log("[INIT] <receive_msg>", "Socket   :[MADE]")
    NF_log("[INIT] <receive_msg>", ":[STARTED]")
    print "[INIT] <receive_msg>", "Socket  :[MADE]"
    print "[INIT] <receive_msg>", "        :[STARTED]"
    time.sleep(1)
    while True:
        raw_received = NF_sock.recv(8192)
        received_queue.append(raw_received)

def init_NF_MW_publish(NF):
    global NF_names, NF_name, NF_id, variable_names, variable_name, variable_id, init_NF_ID, init_PUB_ID

    NF_name = NF_names[NF]
    variable_name = variable_names[NF]

    # msg = Data length(2B)+Kind(2B)+NF_local_ID(2B)+NF_Global_ID(2B)+NF_NAME(nB)
    init_msg = sp("HHHH", 8+len(NF_name), 0, 0, 0)+"".join([sp("c", x) for x in NF_name])
    NF_log("[INIT][OUT] <init_NF_MW_publish>","INIT NF_ID msg made and added to sending_queue")
    sending_queue.append(init_msg)
    while not init_NF_ID:
        time.sleep(1)

    print "********* INIT (NF_ID) ***********"
    print "Registered in Middle-Ware"
    print "My NF_ID : global={}".format(NF_id)
    print "**********************************"
    NF_log("[INIT] <init_NF_MW_publish>","INIT_NF_ID :[DONE]")
    # print "[INIT] <init_NF_MW_publish> INIT_NF_ID :[DONE]\n"

    # msg = Data length(2B)+Kind(2B)+NF_Global_ID(2B)+NF_NAME(nB)
    init_msg = sp("HHH", 6+len(variable_name), 1, NF_id)+"".join([sp("c", x) for x in variable_name])
    NF_log("[INIT][OUT] <init_NF_MW_publish>","INIT PUB_VAR_ID msg made and added to sending_queue")
    sending_queue.append(init_msg)
    while not init_PUB_ID:
        time.sleep(1)

    print "********* INIT (PUB_ID) **********"
    print "My Publish ID : {}".format(variable_id)
    print "**********************************"
    NF_log("[INIT] <init_NF_MW_publish>","PUB_VAR_ID :[DONE]")
    # print "[INIT] <init_NF_MW_publish> PUB_VAR_ID :[DONE]\n"

    time.sleep(5)
    publish_updates()

def msg_cleaner_handler():
    global init_NF_ID, init_PUB_ID, received_queue, NF_id, variable_id, variable_name, var_names_IDs, answer, SUB_ID_ans

    current_data = "" # empty for started
    NF_log("[INIT] <msg_cleaner_handler>",":[STARTED]")
    print "[INIT] <msg_cleaner_handler> :[STARTED]\n"
    while True:
        try:
            current_data += received_queue.pop(0) # pop the first received chunk and add to the remained bytes (if any)

            # more than 2 bytes to know the lenght of the msg AND enough bytes to rebuild a msg
            while (len(current_data)>2 and len(current_data)>=int(su("H",current_data[:2])[0])):
                in_msg = current_data[:int(su("H",current_data[:2])[0])] # we extract the msg

                #### INIT NF_ID REPLY => (kind = 0)
                ## Length(2B)+kind(2B)+NF_global_ID(2B)
                if int(su("H",in_msg[2:4])[0])==0: # it is an NF_global_ID reply from the SDN controller
                    init_NF_ID = 1
                    NF_id = int(su("H",in_msg[6:8])[0]) # NF_global_ID
                    NF_log("[IN] <msg_cleaner_handler>","My NF_ID : global={}".format(NF_id))

                    #### CUT PROCESSED MSG FROM current_data
                    current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg

                #### INIT PUB_variable_ID REPLY => (kind = 1)
                ## Length(2B)+kind(2B)+NF_global_ID(2B)
                elif int(su("H",in_msg[2:4])[0])==1: # it is an PUB_variable_ID reply from the SDN controller
                    init_PUB_ID = 1
                    variable_id = int(su("H",in_msg[6:8])[0]) # PUB_variable_ID
                    var_names_IDs[variable_name] = int(su("H",in_msg[6:8])[0]) # convert and save the Variable_ID
                    NF_log("[IN] <msg_cleaner_handler>","My Publish variable_ID : {}".format(variable_id))
                    update_num = 0 # initializing

                    #### CUT PROCESSED MSG FROM current_data
                    current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg

                #### PUBLISH MSG => (kind = 2)
                ## kind(2B)+variable_id(4B)+update_num(2B)+frag_tot(2B)+frag_num(2B)+DATA(mB)
                elif int(su("H",in_msg[2:4])[0])==2: # it is a publish
                    try:
                        NF_log("[IN] <msg_cleaner_handler>","Received PUBLISH => len({}), kind({})\
                               ".format(su("H",in_msg[:2])[0],msg_kind(int(su("H",in_msg[2:4])[0]))))

                        print "[IN] <msg_cleaner_handler>","Received PUBLISH => len({}), kind({})\
                              ".format(su("H",in_msg[:2])[0],msg_kind(int(su("H",in_msg[2:4])[0])))
                    except:
                        pass

                    # checking if drop mark for "Variable_ID,update_num"
                    if (str(su("H",in_msg[6:8])[0])+","+str(su("H",in_msg[8:10])[0])) not in drop_update.keys():
                        drop_update[str(su("H",in_msg[6:8])[0])+","+str(su("H",in_msg[8:10])[0])] = 0 # do not drop this update
                        ## making a fake last received packet for the first time
                        global_table_last_frame[int(su("H",in_msg[6:8])[0])] = [int(su("H",in_msg[8:10])[0]),
                                                int(su("H",in_msg[10:12])[0]), int(su("H",in_msg[12:14])[0])-1]
                        tmp_recvd_publishes[int(su("H",in_msg[6:8])[0])] = [] # building place for the first msg

                    # there is no drop desicion on this "Variable_ID,update_num"
                    if (drop_update[str(su("H",in_msg[6:8])[0])+","+str(su("H",in_msg[8:10])[0])]) == 0:
                        if global_table_last_frame[int(su("H",in_msg[6:8])[0])][0] == int(su("H",in_msg[8:10])[0]): # from the same update_num
                            if global_table_last_frame[int(su("H",in_msg[6:8])[0])][2]+1 == int(su("H",in_msg[12:14])[0]): # we have normal next fragment

                                 # appending the pure msg to the temporary list for this update_num of this variable_id
                                tmp_recvd_publishes[int(su("H",in_msg[6:8])[0])].append(in_msg[14:])
                                if int(su("H",in_msg[10:12])[0])==int(su("H",in_msg[12:14])[0]): # last fragment of the update
                                    fileName = "logs/P_recv_"+str(su("H",in_msg[6:8])[0]) # making filname for saving data
                                    with open(fileName,"a") as f: # open file for external save(DEBUGING)
                                        f.write("".join(tmp_recvd_publishes[int(su("H",in_msg[6:8])[0])])) # external save
                                    tmp_recvd_publishes[int(su("H",in_msg[6:8])[0])] = [] # cleaning the in_msg for next update

                                    # ready for first fragment of next update
                                    global_table_last_frame[int(su("H",in_msg[6:8])[0])]=[int(su("H",in_msg[8:10])[0])+1,0,0]
                            else: # we have lost fragment/s

                                # puting drop desicion on this "Variable_ID,update_num"
                                # drop_update[str(su("H",in_msg[6:8])[0])+","+str(su("H",in_msg[8:10])[0])] = 1

                                # Data_length(2B)+kind(2B)+Global_ID(2B)+variable_id(2B)+update_num(2B)
                                recover_msg = sp("H",10)+sp("H",6)+sp("H",NF_id)+in_msg[6:10]
                                sending_queue.append(recover_msg)
                                tmp_recvd_publishes[int(su("H",in_msg[6:8])[0])] = [] # cleaning the in_msg due to lost fragment
                        elif int(su("H",in_msg[12:14])[0]) > 1: # we have lost msg from 2 consequent updates
                            # drop_update[str(su("H",in_msg[6:8])[0])+","+str(su("H",in_msg[8:10])[0])] = 1 # puting drop desicion on this "variable_id,update_num"

                            ## Data_length(2B)+kind(2B)+Global_ID(2B)+variable_id(2B)+previous_update_num(2B)
                            recover_msg = sp("H",10)+sp("H",6)+sp("H",NF_id)+in_msg[6:8]+sp("H",int(su("H",in_msg[8:10])[0])-1) #recover for previous update
                            sending_queue.append(recover_msg)
                            tmp_recvd_publishes[int(su("H",in_msg[6:8])[0])-1] = [] # cleaning the in_msg due to lost fragment of previous update

                            ## Data_length(2B)+kind(2B)+Global_ID(2B)+variable_id(2B)+update_num(2B)
                            recover_msg = sp("H",10)+sp("H",6)+sp("H",NF_id)+in_msg[6:10]
                            sending_queue.append(recover_msg)
                            tmp_recvd_publishes[int(su("H",in_msg[6:8])[0])] = [] # cleaning the in_msg due to lost fragment
                    else:
                        tmp_recvd_publishes[int(su("H",in_msg[6:8])[0])] = [] # empty the tempory received update because of fragment/s lost

                    #### CUT PROCESSED MSG FROM current_data
                    current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg

                #### SUBSCRIBE VARIABLE_ID RESPONSE
                elif int(su("H",in_msg[2:4])[0])==5: # it is a SDN reply to variable_ID request for subscription
                    if int(su("H",in_msg[6:8])[0])==0:
                        SUB_ID_ans = "error"
                        NF_log("msg_cleaner_handler", "UN-SUCCESSFUL VAR_ID_REQ response from the SDN")
                        print "msg_cleaner_handler: UN-SUCCESSFUL VAR_ID_REQ response from the SDN"
                    else:
                        SUB_ID_ans = "ok"
                        var_name = "".join([su("c", x)[0] for x in in_msg[8:]]) # the variable_name
                        # print "var_name: ",var_name
                        var_names_IDs[var_name] = int(su("H",in_msg[6:8])[0]) # convert and save the Variable_ID
                        NF_log("msg_cleaner_handler", "SUCCESSFUL VAR_ID_REQ response from the SDN")
                        print "msg_cleaner_handler: SUCCESSFUL VAR_ID_REQ response from the SDN"

                    #### CUT PROCESSED MSG FROM current_data
                    current_data = current_data[int(su("H",current_data[:2])[0]):] # continue from begining of the next msg
                    answer = 1

        except IndexError:
            time.sleep(1)
            pass

def subscribe_on_variable(NF): # SUBSCRIBE 
    global NF_id, variable_name, var_names_IDs, answer, init_SUB_ID, SUB_ID_ans

    while not init_NF_ID:
        time.sleep(1)

    if NF==3:
        variables = [x for x in sorted(var_names_IDs.keys()) if x!=variable_name]
        for i in range(3):
            sub_var_name = variables[i]
            if var_names_IDs[sub_var_name]==0:
                while not init_SUB_ID:

                    # msg = Data_length(2B)+Kind(2B)+NF_Global_ID(2B)+sub_var(nB)
                    var_init_msg = sp("HHH", 6+len(sub_var_name), 5, NF_id)+"".join([sp("c", x) for x in sub_var_name])
                    NF_log("[NF] <subscribe_on_variable>","INIT SUB_VAR_ID msg made and added to sending_queue")
                    sending_queue.append(var_init_msg)

                    while not answer: # wait for the answer from the REPLICA controller
                        time.sleep(1)

                    if SUB_ID_ans=="error": # there is no "variable_id" assigned to that "variable"
                        time.sleep(10)
                        sending_queue.append(var_init_msg)
                        
                    elif SUB_ID_ans=="ok":
                        init_SUB_ID=1
                        
                NF_log("[INFO] <subscribe_on_variable>","SUB_VAR_ID : DONE")
                print "[INFO] <subscribe_on_variable> : SUB_VAR_ID : DONE\n"

            print "........... SUBSCRIBE ..........."
            print "Subscribing from < NF > : {} ".format(NF_id)
            print "Subscribing for the variable_NAME < {} >".format(sub_var_name)
            print "With the variable_ID < {} >".format(var_names_IDs[sub_var_name])
            print "................................."

            # msg = length(2B) + kind(2B) + Global_ID(2B) + variable_id(2B)
            sub_msg = sp("HHHH", 8, 3, NF_id, var_names_IDs[sub_var_name])
            NF_log("subscribe_on_variable","sub_msg to the NF sending_queue")
            sending_queue.append(sub_msg)
            init_SUB_ID = 0
            answer = 0
            SUB_ID_ans = "-"


def main(NF):

    """ (1) receives from socket and writes in received_queue in a loop.  """
    thr_receive = threading.Thread(target=receive_msg)

    """ (1) Connect to MW with a socket on (server_port = 65431) and localhost as address.
        (2) reads from sending_queue and sends to socket in loop.  """
    thr_send = threading.Thread(target=send_msg)

    """ (1) Reads from the received_queue, recover data if needed and do the needed jobs due to msg kind """
    thr_msg_handler = threading.Thread(target=msg_cleaner_handler)

    """ (1) Make an Global_NF_ID request msg, containing the NAME of the NF and puts the msg inside sending_queue.
        (2) If the NF received the Global_NF_ID, make a Variable_ID request and containing the NAME of the variable
            and puts the msg inside sending_queue.
        (3) If the NF received the Variable_ID, it start to publish on the variable.    """
    thr_init_publish = threading.Thread(target=init_NF_MW_publish, args=(NF,))

    """ (1) send a request for SUB_ID to the SDN controller through MW.
        (2) update its internal database.
        (3) send subscription on requested variable_ID/s.   """
    thr_subscribe = threading.Thread(target=subscribe_on_variable, args=(NF,))

    thr_receive.start()
    time.sleep(1)
    thr_send.start()
    time.sleep(1)
    thr_msg_handler.start()
    time.sleep(1)

    thr_init_publish.start()
    time.sleep(20)
    thr_subscribe.start() # can be a function

    thr_send.join()
    thr_receive.join()
    thr_msg_handler.join()
    thr_init_publish.join()
    thr_subscribe.join()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='NF INIT')
    parser.add_argument('--n', help='NF choice', type=int, action="store",
            required=True, default=0)
    args = parser.parse_args()

    main(args.n)
