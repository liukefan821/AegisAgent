// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MockAutomata {
    function verifyAttestation(bytes calldata /* quote */) external pure returns (bool, bytes32) {
        return (true, bytes32(uint256(1)));
    }
}