/**
 * @file opcodes.h
 * @author Remy Nguyen (rnguyen@nrao.edu)
 * @brief Header file that contains opcode declarations for the P1AM-100 PLC.
 * 
 * Each opcode is an 8-bit binary number with the following syntax:
 * - 1-bit warning light bool
 * - 1 for selection operation
 * - 2-bit antenna selection code (00 for EMS, 01 for DFS)
 * - 4-bit RF chain selection code
 * 
 * OR
 * 
 * - 1-bit warning light bool
 * - 0 for config or sleep operation
 * - 6-bit config opcode
 * 
 * Note that the warning light bit is a "don't care" for received opcodes but 
 * is stored and transmitted to the Python program in the status bitmask
 * 
 * @date Last Modified: 2024-08-07
 * 
 * @copyright Copyright (c) 2024
 * 
 */

constexpr uint8_t WLIGHT_ON             = (0b10000000);
constexpr uint8_t WLIGHT_ON_EXCL        = (0b10001111);
constexpr uint8_t WLIGHT_CLR            = (0b01111111);

constexpr uint8_t RETURN_OPCODES        = (0b00000001);
constexpr uint8_t SLEEP                 = (0b00000000);
constexpr uint8_t GET_FW_VERSION        = (0b00000010);
constexpr uint8_t PRINT_MODULES         = (0b00000011);
constexpr uint8_t IS_BASE_ACTIVE        = (0b00000100);
constexpr uint8_t P1_INIT               = (0b00000101);
constexpr uint8_t P1_DISABLE            = (0b00000110);
constexpr uint8_t QUERY_STATUS          = (0b00000111);
constexpr uint8_t CHECK_24V_SL1         = (0b00001001);
constexpr uint8_t CHECK_24V_SL2         = (0b00001010);
constexpr uint8_t CHECK_24V_SL3         = (0b00001011);
constexpr uint8_t WLIGHT_EXCL           = (0b00001111);
constexpr uint8_t READ_STATUS_SL1       = (0b00010001);
constexpr uint8_t READ_STATUS_SL2       = (0b00010010);
constexpr uint8_t READ_STATUS_SL3       = (0b00010011);

constexpr uint8_t EMS_SELECT            = (0b01000000);
constexpr uint8_t DFS_SELECT            = (0b01010000);

constexpr uint8_t CH1_SELECT            = (0b01000000);
constexpr uint8_t CH2_SELECT            = (0b01000001);
constexpr uint8_t CH3_SELECT            = (0b01000010);
constexpr uint8_t CH4_SELECT            = (0b01000011);
constexpr uint8_t CH5_SELECT            = (0b01000100);
constexpr uint8_t CH6_SELECT            = (0b01000101);
constexpr uint8_t CH7_SELECT            = (0b01000110);
constexpr uint8_t CH8_SELECT            = (0b01000111);
constexpr uint8_t CH9_SELECT            = (0b01001000);
constexpr uint8_t CH10_SELECT           = (0b01001001);
constexpr uint8_t CH11_SELECT           = (0b01001010);
constexpr uint8_t CH12_SELECT           = (0b01001011);
constexpr uint8_t CH13_SELECT           = (0b01001100);
constexpr uint8_t CH14_SELECT           = (0b01001101);
constexpr uint8_t CH15_SELECT           = (0b01001110);
constexpr uint8_t CH16_SELECT           = (0b01001111);

