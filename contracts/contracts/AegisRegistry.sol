// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title AegisRegistry
 * @notice Manages and maintains the whitelist of trusted TEE Enclave image hashes (mrEnclave).
 * @dev Only mrEnclave hashes registered in this contract can have their instructions executed by the Vault.
 */
contract AegisRegistry {
    /// @notice The address of the contract administrator
    address public owner;
    
    /// @dev Mapping to store the registration status of each enclave hash
    mapping(bytes32 => bool) private _registeredAgents;
    
    /// @dev Array to store the list of all registered enclave hashes for enumeration
    bytes32[] private _agentList;

    /**
     * @notice Emitted when a new TEE image hash is added to the whitelist.
     * @param mrEnclave The unique identity hash of the TEE environment.
     * @param registrar The address that performed the registration.
     * @param timestamp The block timestamp when the registration occurred.
     */
    event AgentRegistered(bytes32 indexed mrEnclave, address indexed registrar, uint256 timestamp);

    /**
     * @dev Throws if called by any account other than the owner.
     */
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call this");
        _;
    }

    /**
     * @dev Initializes the contract setting the deployer as the initial owner.
     */
    constructor() {
        owner = msg.sender;
    }

    /**
     * @notice Adds a new TEE image hash to the whitelist.
     * @dev Only the contract owner can call this function.
     * @param mrEnclave The unique identity hash of the TEE environment.
     */
    function registerAgent(bytes32 mrEnclave) external onlyOwner {
        require(!_registeredAgents[mrEnclave], "Agent already registered");
        _registeredAgents[mrEnclave] = true;
        _agentList.push(mrEnclave);
        emit AgentRegistered(mrEnclave, msg.sender, block.timestamp);
    }

    /**
     * @notice Checks if a given mrEnclave is registered in the whitelist.
     * @param mrEnclave The TEE hash to check.
     * @return True if the hash is registered, false otherwise.
     */
    function isRegistered(bytes32 mrEnclave) external view returns (bool) {
        return _registeredAgents[mrEnclave];
    }

    /**
     * @notice Returns the complete list of all registered agent hashes.
     * @return An array containing all registered mrEnclave hashes.
     */
    function getRegisteredAgents() external view returns (bytes32[] memory) {
        return _agentList;
    }
}