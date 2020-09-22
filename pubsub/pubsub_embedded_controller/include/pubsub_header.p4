/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

#ifndef __HEADER__
#define __HEADER__

#include "pubsub_define.p4"

header ethernet_t {
    mac_addr_t   dstAddr;
    mac_addr_t   srcAddr;
    ether_type_t etherType;
}

header ipv4_t {
    bit<4>      version;
    bit<4>      ihl;
    bit<8>      diffserv;
    bit<16>     totalLen;
    bit<16>     identification;
    bit<3>      flags;
    bit<13>     fragOffset;
    bit<8>      ttl;
    bit<8>      protocol;
    bit<16>     hdrChecksum;
    ipv4_addr_t srcAddr;
    ipv4_addr_t dstAddr;
}

header tcp_t {
    bit<16>  srcPrt;
    bit<16>  dstPrt;
    bit<32>  seqNo;
    bit<32>  ackNo;
    bit<4>   dataOffset;
    bit<3>   res;
    bit<3>   ecn;
    bit<6>   ctrl;
    bit<16>  window;
    bit<16>  chksum;
    bit<16>  urgentPtr;
   
}

header udp_t {
    bit<16> srcPrt;
    bit<16> dstPrt;  // here 65432(0xff98) => ip.dst is pubsub header
    bit<16> lenght;
    bit<16> chksum;
}

@controller_header("packet_in")
header packet_in_header_t {
    bit<16> input_port;
}

@controller_header("packet_out")
header packet_out_header_t {
    bit<16> output_port;
}

struct local_metadata_t {
    bit<4> mcastGrp_id;       // The id of multi_cast group to be set for output.
    bit<4> port_indx;         // The input port_mask number for incoming sub packet.

    bit<22> pubsub_indx;      // The (pub or sub) index for temp use.
    bit<2> pubsub_flags;      // '11'=sub_add, '10'=sub_rem, '00'=pub,
                              // '01'=(send to SDN controller(INIT, SUB_REQUEST, RECOVER)).
    bit<8> ipDstCode;
    bit<8> ipSrcCode;
}

struct headers {
    packet_in_header_t packet_in;
    packet_out_header_t packet_out;
    ethernet_t   ethernet;
    ipv4_t       ipv4;
    tcp_t        tcp;
    udp_t        udp;
}

#endif
