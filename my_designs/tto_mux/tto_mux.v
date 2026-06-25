module tto_mux (A, B, S, Y);
    input  A, B, S;
    output Y;

    wire S_n, G1, G2;

    // Instantiate sky130 primitives directly
    // Yosys cannot re-optimise already-mapped gate instances
    sky130_fd_sc_hd__inv_1  U_INV (.A(S),   .Y(S_n));
    sky130_fd_sc_hd__and2_1 U_AND1(.A(A),   .B(S_n), .X(G1));
    sky130_fd_sc_hd__and2_1 U_AND2(.A(B),   .B(S),   .X(G2));
    sky130_fd_sc_hd__or2_1  U_OR  (.A(G1),  .B(G2),  .X(Y));

endmodule
