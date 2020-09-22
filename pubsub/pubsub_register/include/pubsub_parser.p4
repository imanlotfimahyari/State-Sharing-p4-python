/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

#ifndef __PARSER__
#define __PARSER__

#include "pubsub_define.p4"

parser MyParser(packet_in packet,
                out headers hdr,
                inout local_metadata_t local_metadata,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            ETHER_TYPE_IPV4  : parse_ipv4;
            default    : accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol) {
            PROTO_UDP   : parse_udp;
            PROTO_TCP   : parse_tcp;
            default    : accept;
        }
    }

    state parse_tcp {
        packet.extract(hdr.tcp);
        transition select(hdr.tcp.dstPrt) {
            default      : accept;
        }
    }

    state parse_udp {
        packet.extract(hdr.udp);
        transition select(hdr.udp.dstPrt) {
            default      : accept;
        }
    }
}

/*************************************************************************
**************************  D E P A R S E R  *****************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.ipv4);
        packet.emit(hdr.tcp); 
        packet.emit(hdr.udp);
    }
}

#endif
