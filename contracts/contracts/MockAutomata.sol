// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MockAutomata {
    // 模拟 TEE 验证逻辑，永远返回验证成功，镜像哈希为 0x01
    function verifyAttestation(bytes calldata /* quote */) external pure returns (bool, bytes32) {
        return (true, bytes32(uint256(1)));
    }
}