#!/usr/bin/env python2

import argparse, grpc, os, sys, json
from time import sleep
from struct import unpack as su
from struct import pack as sp
from scapy.all import *

# Import P4Runtime lib from parent utils dir
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
        '../../utils/'))

from p4runtime_lib.error_utils import printGrpcError
from p4runtime_lib.switch import ShutdownAllSwitchConnections
import p4runtime_lib.helper as helper
import p4runtime_lib.bmv2


## GENERAL
def printGrpcError(e):
    print "gRPC Error: ", e.details(),
    status_code = e.code()
    print "(%s)" % status_code.name,
    # detail about sys.exc_info - https://docs.python.org/2/library/sys.html#sys.exc_info
    traceback = sys.exc_info()[2]
    print "[%s:%s]" % (traceback.tb_frame.f_code.co_filename, traceback.tb_lineno)

# object hook for josn library, use str instead of unicode object
# https://stackoverflow.com/questions/956867/how-to-get-string-objects-instead-of-unicode-from-json
def json_load_byteified(file_handle):
    return _byteify(json.load(file_handle, object_hook=_byteify),
                    ignore_dicts=True)

def _byteify(data, ignore_dicts=False):
    # if this is a unicode string, return its string representation
    if isinstance(data, unicode):
        return data.encode('utf-8')
    # if this is a list of values, return list of byteified values
    if isinstance(data, list):
        return [_byteify(item, ignore_dicts=True) for item in data]
    # if this is a dictionary, return dictionary of byteified keys and values
    # but only if we haven't already byteified it
    if isinstance(data, dict) and not ignore_dicts:
        return {
            _byteify(key, ignore_dicts=True): _byteify(value, ignore_dicts=True)
            for key, value in data.iteritems()
        }
    # if it's anything else, return it in its original form
    return data

## PACKET_IN BY GRPC(P4RUNTIME)
def packet_in_metadata(pkt_in):
    pkt_in_metadata={}
    print("Received Packet-in\n")
    packet = pkt_in.packet.payload
    metadata = pkt_in.packet.metadata
    for meta in metadata:
        metadata_id = meta.metadata_id
        value = meta.value
        pkt_in_metadata[metadata_id]=value
    input_port=int(su("!H",pkt_in_metadata[1])[0])
    tmp_pkt = copy.deepcopy(packet)
    tmp_pkt1 = Ether(_pkt=tmp_pkt)
    raw_var_id=[bin(int(x))[2:].zfill(8) for x in tmp_pkt1[IP].dst[4:].split(".")]
    var_id=int(raw_var_id[0][2:]+raw_var_id[1]+raw_var_id[2],2)
    print tmp_pkt1[IP].dst
    print "var_id: ",var_id

    return packet, pkt_in_metadata, input_port, var_id

## Table Read and Manipulate
def readTableRules(p4info_helper, sw, table):
    """
    Reads the table entries from all tables on the switch.
    :param p4info_helper: the P4Info helper
    :param sw: the switch connection
    """
    print '\n----- Reading tables rules for %s -----' % sw.name
    ReadTableEntries1 = {'table_entries': []}
    ReadTableEntries2 = []
    for response in sw.ReadTableEntries():
        for entity in response.entities:
            ReadTableEntry = {}
            entry = entity.table_entry
            table_name = p4info_helper.get_tables_name(entry.table_id)
            if table==None or table==table_name:
            # if table==None:
                ReadTableEntry['table'] = table_name
                print '%s: ' % table_name,
                for m in entry.match:
                    print p4info_helper.get_match_field_name(table_name, m.field_id),
                    try:
                        print "\\x00"+"".join("\\x"+"{:02x}".format(ord(c)) for c in "".join([d for d in (p4info_helper.get_match_field_value(m))])),
                    except:
                        print '%r' % (p4info_helper.get_match_field_value(m),),
                    match_name = p4info_helper.get_match_field_name(table_name, m.field_id)
                    tmp_match_value = (p4info_helper.get_match_field_value(m),)
                    ReadTableEntry['match']={}
                    ReadTableEntry['match'][match_name] = tmp_match_value
                action = entry.action.action
                action_name = p4info_helper.get_actions_name(action.action_id)
                ReadTableEntry['action_name'] = action_name
                print '->', action_name,
                for p in action.params:
                    print p4info_helper.get_action_param_name(action_name, p.param_id),
                    print '%r' % p.value,
                    action_params = p4info_helper.get_action_param_name(action_name, p.param_id)
                    tmp_action_value = p.value
                    ### possibly needs bytify =>> struct. pack and unpack
                    ReadTableEntry['action_params'] = {}
                    ReadTableEntry['action_params'][action_params] = tmp_action_value
                print
                ReadTableEntries1.setdefault('table_entries',[]).append(ReadTableEntry)
                ReadTableEntries2.append(ReadTableEntry)
    return ReadTableEntries2

def writeL2Publish(p4info_helper, sw, var_id, mc_grp_id):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.L2_publish",
        match_fields={"local_metadata.pubsub_indx": var_id},
        # default_action=default_action,
        action_name="MyIngress.set_mcast_grp",
        action_params={"st_mc_grp": mc_grp_id})
    sw.WriteTableEntry(table_entry)
    print "Installed L2_Publish rule via P4Runtime."

def modifyL2Publish(p4info_helper, sw, var_id, mc_grp_id):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.L2_publish",
        match_fields={"local_metadata.pubsub_indx": var_id},
        # default_action=default_action,
        action_name="MyIngress.set_mcast_grp",
        action_params={"st_mc_grp": mc_grp_id})
    sw.ModifyTableEntry(table_entry)
    print "Installed(Modified) L2_Publish rule via P4Runtime."

def deleteL2Publish(p4info_helper, sw, var_id, mc_grp_id):
    table_entry = p4info_helper.buildTableEntry(
        table_name="MyIngress.L2_publish",
        match_fields={"local_metadata.pubsub_indx": var_id},
        # default_action=default_action,
        action_name="MyIngress.set_mcast_grp",
        action_params={"st_mc_grp": mc_grp_id})
    sw.DeleteTableEntry(table_entry)
    print "Removed L2_Publish rule via P4Runtime."

def port_mask(port):
    port_mask=1<<(int(port)-1)
    # port_mask=2**(int(port)-1)
    return port_mask



def main(p4info_file_path, bmv2_file_path, sw_num):
    # Instantiate a P4Runtime helper from the p4info file
    p4info_helper = helper.P4InfoHelper(p4info_file_path)
    s_name='s'+str(sw_num)
    print "switch name: ", s_name

    try:
        '''
         Create a switch connection object for s1
         This is backed by a P4Runtime gRPC connection.
         Also, dump all P4Runtime messages sent to switch to given txt files.
         In the P4 package here, port no starts from 50051
        '''
        switch = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name=s_name,
            address='127.0.0.1:5005'+str(sw_num),
            device_id=0,
            proto_dump_file='logs/'+s_name+'-p4runtime-requests.txt')

        '''
         Send master arbitration update message to establish this controller as
         master (required by P4Runtime before performing any other write operation)
        '''
        switch.MasterArbitrationUpdate()
        print "Master arbitration done..."
        readTableRules(p4info_helper, switch, None)
        print
        print " <<<< CONTROLLER READEY! WAITING FOR PACKET_IN >>>> "
        while True:
            ''' USING P4RUNTIME AS RECEIVER FOR PACKET_IN IN THE EMBEDDED CONTROLLER '''
            packetin = switch.PacketIn()
            if packetin.WhichOneof('update')=='packet':
                packet, pkt_in_metadata, input_port, var_id = packet_in_metadata(packetin)
                input_port_mask = port_mask(input_port)

                print "BEFORE WRITING"
                current_table = readTableRules(p4info_helper, switch, "MyIngress.L2_publish")
                print

                if len(current_table)==0:
                    try:
                        writeL2Publish(p4info_helper, switch, var_id, input_port_mask)
                    except:
                        print "\nproblem writing table for them!\n"
                        raise
                else:
                    found=False
                    for tbl_entry in current_table:
                        tmp_match_value = '\x00'+tbl_entry['match']['local_metadata.pubsub_indx'][0]
                        if su("!I",tmp_match_value)==var_id:
                            old_mc_grp_id = su("!H", tbl_entry['action_params']['st_mc_grp'])
                            new_mc_grp_id = old_mc_grp_id | input_port_mask
                            try:
                                ## DELETE and WRITE
                                deleteL2Publish(p4info_helper, switch, var_id, old_mc_grp_id)
                                writeL2Publish(p4info_helper, switch, var_id, new_mc_grp_id)
                                ## OR
                                ## MODIFY
                                # modifyL2Publish(p4info_helper, switch, var_id, new_mc_grp_id)
                            except:
                                print "\nproblem writing table for them!\n"
                                # raise
                            found=True
                            break
                    if not found:
                        try:
                            writeL2Publish(p4info_helper, switch, var_id, input_port_mask)
                        except:
                            print "\nproblem writing table for them!\n"
                            raise
            # '''
            # USING P4RUNTIME FOR PACKET_OUT IN THE CONTROLLER
            # '''
            # my_packet_out = p4info_helper.buildPacketOut(
            #     payload = packet,
            #     metadata = {
            #         1: pkt_in_metadata[1]

    except KeyboardInterrupt:
        # using ctrl + c to exit
        # Then close all the connections
        print " Shutting down....."
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
            type=str, action="store", required=False,
            default='./build/pub_sub.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
            type=str, action="store", required=False,
            default='./build/pub_sub.json')
    parser.add_argument('--sw', help='switch number',
            type=int, action="store", required=False,
            default=1)

    args = parser.parse_args()

    if not os.path.exists(args.p4info):
        parser.print_help()
        print "\np4info file not found: {}, Have you run 'make'?".format(args.p4info)
        parser.exit(1)
    if not os.path.exists(args.bmv2_json):
        parser.print_help()
        print "\nBMv2 JSON file not found: {}, Have you run 'make'?".format(args.bmv2_json)
        parser.exit(1)

    # Pass argument into main function
    main(args.p4info, args.bmv2_json, args.sw)
