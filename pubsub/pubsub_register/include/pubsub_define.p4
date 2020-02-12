/*************************************************************************
************************* D E F I N E  ***********************************
*************************************************************************/

#ifndef __DEFINE__
#define __DEFINE__

typedef bit<16> ether_type_t;
typedef bit<48> mac_addr_t;
typedef bit<9>  port_num_t;
typedef bit<32> ipv4_addr_t;

const bit<16> ETHER_TYPE_IPV4 = 0x0800;
const bit<8> PROTO_UDP = 0x11;

//const bit<32> TEST_VALUE = 1 ;

#endif
