"""
 * @file opcodes.py
 * @author Remy Nguyen (rnguyen@nrao.edu)
 * @brief Header file that contains opcode declarations for the P1AM-100 PLC.
 * 
 * Each opcode is an 8-bit binary number with the following syntax:
 * - Leading 1
 * - 1 for selection operation
 * - 2-bit antenna selection code (00 for EMS, 01 for DFS)
 * - 4-bit RF chain selection code
 * 
 * OR
 * 
 * - Leading 1
 * - 0 for config or sleep operation
 * - 6-bit config opcode
 *
 * Due to the way the PLC is written to parse inputs, each opcode MUST be terminated by a newline (\n) character.
 * 
 * @date Last Modified: 2024-08-07
 * 
 * @copyright Copyright (c) 2024
 * 
 """

from enum import Enum

class opcodes(Enum):
    WLIGHT_ON             = (0b10000000);
    WLIGHT_TOGGLE         = (0b00001111);
    WLIGHT_CLR            = (0b01111111);

    RETURN_OPCODES        = (0b00000001);
    SLEEP                 = (0b00000000);
    GET_FW_VERSION        = (0b00000010);
    PRINT_MODULES         = (0b00000011);
    IS_BASE_ACTIVE        = (0b00000100);
    P1_INIT               = (0b00000101);
    P1_DISABLE            = (0b00000110);
    QUERY_STATUS          = (0b00000111);
    CHECK_24V_SL1         = (0b00001001);
    CHECK_24V_SL2         = (0b00001010);
    CHECK_24V_SL3         = (0b00001011);
    WLIGHT_EXCL           = (0b00001111);
    READ_STATUS_SL1       = (0b00010001);
    READ_STATUS_SL2       = (0b00010010);
    READ_STATUS_SL3       = (0b00010011);

    EMS_SELECT            = (0b01000000);
    DFS_SELECT            = (0b01010000);
    CH1_SELECT            = (0b01000000);
    CH2_SELECT            = (0b01000001);
    CH3_SELECT            = (0b01000010);
    CH4_SELECT            = (0b01000011);
    CH5_SELECT            = (0b01000100);
    CH6_SELECT            = (0b01000101);
    CH7_SELECT            = (0b01000110);
    CH8_SELECT            = (0b01000111);
    CH9_SELECT            = (0b01001000);
    CH10_SELECT           = (0b01001001);
    CH11_SELECT           = (0b01001010);
    CH12_SELECT           = (0b01001011);
    CH13_SELECT           = (0b01001100);
    CH14_SELECT           = (0b01001101);
    CH15_SELECT           = (0b01001110);
    CH16_SELECT           = (0b01001111);

    EMS_CHAIN1 = EMS_SELECT | CH1_SELECT
    DFS_CHAIN1 = DFS_SELECT | CH1_SELECT