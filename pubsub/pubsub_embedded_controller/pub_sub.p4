/******************* -*- P4_16 -*- *****************/
/******** pubsub <<Embedded controller with P4RUNTIME>> ***********/

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

    action original_inport() {
        local_metadata.port_indx = (bit<4>)1 << (bit<4>)hdr.packet_out.output_port[3:0];
    }

    action send_to_cpu() {
        standard_metadata.egress_spec = CPU_PORT;
        hdr.packet_in.setValid();
        hdr.packet_in.input_port = (bit<16>)standard_metadata.ingress_port;
    }

    action clone3_to_cpu() {
        // Cloning is achieved by using a v1model-specific primitive. Here we
        // set the type of clone operation (ingress-to-egress pipeline), the
        // clone session ID (the CPU one), and the metadata fields we want to
        // preserve for the cloned packet replica.
        clone3(CloneType.I2E, CPU_CLONE_SESSION_ID, standard_metadata.ingress_port );
//        hdr.packet_in.setValid();
//        hdr.packet_in.input_port = (bit<16>)standard_metadata.ingress_port;
    }

    action clone_to_cpu() {
        // Cloning is achieved by using a v1model-specific primitive. Here we
        // set the type of clone operation (ingress-to-egress pipeline), the
        // clone session ID (the CPU one), and the metadata fields we want to
        // preserve for the cloned packet replica.
        clone(CloneType.I2E, CPU_CLONE_SESSION_ID);
//        hdr.packet_in.setValid();
//        hdr.packet_in.input_port = (bit<16>)standard_metadata.ingress_port;
    }

    action set_mcast_grp(port_num_t st_mc_grp) {
        standard_metadata.mcast_grp = (bit<16>)st_mc_grp;
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

    table distribution_tree_pubsub_lpm {
        key = {
            hdr.ipv4.dstAddr: lpm;
        }
        actions = {
            pubsub_reg_forward;
            drop;
        }
        size = 1024;
        default_action = drop();
    }

    table L2_publish {
        key = {
            local_metadata.pubsub_indx: exact;
        }
        actions = {
            set_mcast_grp;
            drop;
        }
        size = 1024;
        default_action = drop();
    }

    apply {
        if(hdr.packet_out.isValid()) { // PACKET FROM CPU (stored SUBSCRIBE)
            original_inport();
            hdr.packet_out.setInvalid();
            distribution_tree_pubsub_lpm.apply();
            return;
        }
        else if (hdr.ipv4.isValid()) {
            ipCode();

            if (local_metadata.ipDstCode == 239 && hdr.udp.isValid() && hdr.udp.dstPrt == 65432) {
                check_flags_plus_in_port_mask();

                if (local_metadata.pubsub_flags == 0) { // PUBLISH
                    L2_publish.apply();
                }
                else if (local_metadata.pubsub_flags == 2) { // SUBSCRIBE remove
//                    clone_to_cpu();
//                    distribution_tree_pubsub_lpm.apply();
                    send_to_cpu();
                }
                else if (local_metadata.pubsub_flags == 3) { // SUBSCRIBE register
//                    clone_to_cpu();
//                    distribution_tree_pubsub_lpm.apply();
                    send_to_cpu();
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
                 inout local_metadata_t local_metadata,
                 inout standard_metadata_t standard_metadata) {


//     action drop() {
//         mark_to_drop(standard_metadata);
//     }
//
//     table distribution_tree_pubsub_lpm {
//         key = {
//             hdr.ipv4.dstAddr: lpm;
//         }
//         actions = {
//             pubsub_reg_forward;
//             drop;
//         }
//         size = 1024;
//         default_action = drop();
//     }

     apply {
//          if (standard_metadata.instance_type == 1) {
//              distribution_tree_pubsub_lpm.apply();
//             hdr.packet_in.setValid();
//             hdr.packet_in.input_port = (bit<16>)standard_metadata.ingress_port; // need to fix this!!!!!
//          }
    }
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
