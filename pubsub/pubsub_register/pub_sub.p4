/******************* -*- P4_16 -*- *****************/
/******** pubsub s1-h4 <<no controller REGISTERS (add/remove)>> ***********/

#include <core.p4>
#include <v1model.p4>
#include "include/pubsub_define.p4"
#include "include/pubsub_header.p4"
#include "include/pubsub_parser.p4"
#include "include/pubsub_checksum.p4"

/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout local_metadata_t local_metadata,
                  inout standard_metadata_t standard_metadata) {

    register<bit<4>>(16) subIndxPort;
//    register<bit<16>>(TEST_VALUE) subIndxPort1;

    action drop() {
        mark_to_drop(standard_metadata);
    }

    action ipCode() {
        local_metadata.ipDstCode = hdr.ipv4.dstAddr[31:24];
   }

    action check_flags_plus_in_port_mask() {
        bit<9> tmp1;
        bit<32> tmp2;

        tmp1 = standard_metadata.ingress_port - 1;
        local_metadata.port_indx = (bit<4>)1 << (bit<4>)tmp1[3:0];

        tmp2 = hdr.ipv4.dstAddr;
        local_metadata.pubsub_flags = (bit<2>)tmp2[23:22];
        local_metadata.pubsub_indx = (bit<22>)tmp2[21:0];
    }

    action update_registers_subscribe() {
        bit<4> tmp;

        subIndxPort.read(tmp, (bit<32>)(local_metadata.pubsub_indx - 1));
        subIndxPort.write((bit<32>)(local_metadata.pubsub_indx - 1), (tmp | local_metadata.port_indx));
    }

    action update_registers_unsubscribe() {
        bit<4> tmp;

        subIndxPort.read(tmp, (bit<32>)(local_metadata.pubsub_indx - 1));
        subIndxPort.write((bit<32>)(local_metadata.pubsub_indx - 1), (tmp ^ local_metadata.port_indx));
    }

    action publish() {
        bit<22> tmp1;
        bit<4> tmp2;

        tmp1 = local_metadata.pubsub_indx - 1;
        subIndxPort.read(tmp2, (bit<32>)tmp1);
        local_metadata.mcastGrp_id = tmp2;
    }

    action set_mcast_grp() {
        standard_metadata.mcast_grp = (bit<16>)local_metadata.mcastGrp_id;
    }

    action send_sub_confirm() {
        bit<32> tmp;

        // CAN BE REMOVED ,USED FOR SCAPY RECEIVE
        tmp = hdr.ipv4.dstAddr;
        hdr.ipv4.dstAddr = hdr.ipv4.srcAddr;
        hdr.ipv4.srcAddr = tmp;
        standard_metadata.egress_spec = standard_metadata.ingress_port;
    }

    action ipv4_forward(mac_addr_t dstAddr, port_num_t port) {
        standard_metadata.egress_spec = port;
        hdr.ethernet.srcAddr = hdr.ethernet.dstAddr;
        hdr.ethernet.dstAddr = dstAddr;
        hdr.ipv4.ttl = hdr.ipv4.ttl - 1;
    }

    action pubsub_reg_forward(port_num_t st_mc_grp) {
        bit<4> tmp;

        tmp = local_metadata.port_indx;
        standard_metadata.mcast_grp = (bit<16>)(~tmp & (bit<4>)st_mc_grp);
    }

    table ipv4_lpm {
        key = {
            hdr.ipv4.dstAddr: lpm;
        }
        actions = {
            ipv4_forward;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = drop();
    }

    table spanning_tree_pubsub_lpm {
        key = {
            hdr.ipv4.dstAddr: lpm;
        }
        actions = {
            pubsub_reg_forward;
            drop;
            NoAction;
        }
        size = 1024;
        default_action = drop();
    }

    apply {
        if (hdr.ipv4.isValid()) {
            ipCode();

            if (local_metadata.ipDstCode == 239 && hdr.udp.isValid() && hdr.udp.dstPrt == 65432) {
                check_flags_plus_in_port_mask();

                if (local_metadata.pubsub_flags == 0) { // PUBLISH
                    publish();
                    set_mcast_grp();
                }
                else if (local_metadata.pubsub_flags == 2) { // SUBSCRIBE remove
                    update_registers_unsubscribe();
                    spanning_tree_pubsub_lpm.apply();
                }
                else if (local_metadata.pubsub_flags == 3) { // SUBSCRIBE register
                    update_registers_subscribe();
                    spanning_tree_pubsub_lpm.apply();
                }
            }

            else {
                ipv4_lpm.apply();
            }
        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout local_metadata_t meta,
                 inout standard_metadata_t standard_metadata) {
    apply {  }
}
/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;
