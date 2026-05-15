// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AegisRegistry
 * @notice 负责管理和维护受信任的 TEE Enclave 镜像哈希（mrEnclave）
 * @dev 只有在这个合约中登记过的 mrEnclave，其发出的指令才会被金库执行
 */
contract AegisRegistry {
    address public owner;
    
    // 存储已注册的 enclave 哈希
    mapping(bytes32 => bool) private _registeredAgents;
    bytes32[] private _agentList;

    event AgentRegistered(bytes32 indexed mrEnclave, address indexed registrar, uint256 timestamp);

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /**
     * @notice 将新的 TEE 镜像哈希加入白名单
     * @param mrEnclave TEE 环境的唯一标识哈希
     */
    function registerAgent(bytes32 mrEnclave) external onlyOwner {
        require(!_registeredAgents[mrEnclave], "Agent already registered");
        _registeredAgents[mrEnclave] = true;
        _agentList.push(mrEnclave);
        emit AgentRegistered(mrEnclave, msg.sender, block.timestamp);
    }

    /**
     * @notice 检查给定的 mrEnclave 是否已注册
     */
    function isRegistered(bytes32 mrEnclave) external view returns (bool) {
        return _registeredAgents[mrEnclave];
    }

    /**
     * @notice 获取所有已注册的 agent 列表
     */
    function getRegisteredAgents() external view returns (bytes32[] memory) {
        return _agentList;
    }
}