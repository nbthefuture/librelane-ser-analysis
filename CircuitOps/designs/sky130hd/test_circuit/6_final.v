module test_circuit (match,
    A,
    B);
 output match;
 input [3:0] A;
 input [3:0] B;

 wire _00_;
 wire _01_;
 wire _02_;
 wire _03_;
 wire _04_;
 wire _05_;
 wire _06_;
 wire _07_;
 wire _08_;
 wire _09_;
 wire net1;
 wire net2;
 wire net3;
 wire net4;
 wire net5;
 wire net6;
 wire net7;
 wire net8;
 wire net9;

 sky130_fd_sc_hd__nor2_1 _10_ (.A(net4),
    .B(net8),
    .Y(_00_));
 sky130_fd_sc_hd__and2_1 _11_ (.A(net4),
    .B(net8),
    .X(_01_));
 sky130_fd_sc_hd__and2_1 _12_ (.A(net2),
    .B(net6),
    .X(_02_));
 sky130_fd_sc_hd__nor2_1 _13_ (.A(net2),
    .B(net6),
    .Y(_03_));
 sky130_fd_sc_hd__o22ai_1 _14_ (.A1(_00_),
    .A2(_01_),
    .B1(_02_),
    .B2(_03_),
    .Y(_04_));
 sky130_fd_sc_hd__and2_1 _15_ (.A(net5),
    .B(net1),
    .X(_05_));
 sky130_fd_sc_hd__nor2_1 _16_ (.A(net5),
    .B(net1),
    .Y(_06_));
 sky130_fd_sc_hd__and2_1 _17_ (.A(net3),
    .B(net7),
    .X(_07_));
 sky130_fd_sc_hd__nor2_1 _18_ (.A(net3),
    .B(net7),
    .Y(_08_));
 sky130_fd_sc_hd__o22ai_1 _19_ (.A1(_05_),
    .A2(_06_),
    .B1(_07_),
    .B2(_08_),
    .Y(_09_));
 sky130_fd_sc_hd__nor2_1 _20_ (.A(_04_),
    .B(_09_),
    .Y(net9));
 sky130_fd_sc_hd__decap_3 PHY_EDGE_ROW_0_Right_0 ();
 sky130_fd_sc_hd__decap_3 PHY_EDGE_ROW_1_Right_1 ();
 sky130_fd_sc_hd__decap_3 PHY_EDGE_ROW_2_Right_2 ();
 sky130_fd_sc_hd__decap_3 PHY_EDGE_ROW_3_Right_3 ();
 sky130_fd_sc_hd__decap_3 PHY_EDGE_ROW_0_Left_4 ();
 sky130_fd_sc_hd__decap_3 PHY_EDGE_ROW_1_Left_5 ();
 sky130_fd_sc_hd__decap_3 PHY_EDGE_ROW_2_Left_6 ();
 sky130_fd_sc_hd__decap_3 PHY_EDGE_ROW_3_Left_7 ();
 sky130_fd_sc_hd__clkbuf_1 input1 (.A(A[0]),
    .X(net1));
 sky130_fd_sc_hd__clkbuf_1 input2 (.A(A[1]),
    .X(net2));
 sky130_fd_sc_hd__clkbuf_1 input3 (.A(A[2]),
    .X(net3));
 sky130_fd_sc_hd__clkbuf_1 input4 (.A(A[3]),
    .X(net4));
 sky130_fd_sc_hd__clkbuf_1 input5 (.A(B[0]),
    .X(net5));
 sky130_fd_sc_hd__clkbuf_1 input6 (.A(B[1]),
    .X(net6));
 sky130_fd_sc_hd__clkbuf_1 input7 (.A(B[2]),
    .X(net7));
 sky130_fd_sc_hd__clkbuf_1 input8 (.A(B[3]),
    .X(net8));
 sky130_fd_sc_hd__buf_2 output9 (.A(net9),
    .X(match));
endmodule
