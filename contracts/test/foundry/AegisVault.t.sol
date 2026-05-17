// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "./Handler.t.sol";
import "../../contracts/AegisVault.sol";
import "../../contracts/AegisRegistry.sol";
import "../../contracts/AegisVerifier.sol";
import "../../contracts/MockAutomata.sol";

/**
 * @title AegisVaultInvariantTest
 * @notice Invariant test suite for the AegisVault contract using the Handler pattern.
 * @dev These tests ensure that the system's "fundamental truths" are never broken 
 * across thousands of random transaction sequences.
 */
contract AegisVaultInvariantTest is Test {
    AegisVault public vault;
    AegisRegistry public registry;
    Handler public handler;

    /**
     * @dev Sets up the testing environment, deploying core contracts and the Handler.
     */
    function setUp() public {
        registry = new AegisRegistry();
        
        // 【升级点】：使用真实的 Mock 合约，而不是 0x1 地址，避免底层 revert
        MockAutomata mock = new MockAutomata();
        AegisVerifier verifier = new AegisVerifier(address(mock));
        
        vault = new AegisVault(address(registry), address(verifier));
        
        // Initialize the Handler to manage randomized state transitions
        handler = new Handler(vault);
        
        // Instruct Foundry to target the Handler contract for fuzzing
        targetContract(address(handler));
    }

    /**
     * @notice Invariant 1: Solvency - Total vault balance must always match user accounting.
     * @dev The actual ETH balance of the vault contract must always be equal to 
     * the sum of all balances tracked within the Handler's ghost state.
     */
    function invariant_Solvency() public view {
        assertEq(address(vault).balance, handler.totalGhostBalance());
    }

    /**
     * @notice Invariant 2: Emergency Stop Integrity.
     * @dev Once a user triggers the emergency stop, all agent authorizations 
     * for that specific user must be instantly invalidated regardless of input.
     * @param user The address of the user to test.
     * @param agent The identity hash of a potential TEE agent.
     */
    function testFuzz_EmergencyStop(address user, bytes32 agent) public {
        vm.prank(user);
        vault.emergencyStop();
        assertEq(vault.isAgentAuthorizedFor(user, agent), false);
    }

    /**
     * @notice Invariant 3: Authorization Integrity - Unregistered agents remain inactive.
     * @dev Ensures that an agent hash that has never been added to the AegisRegistry 
     * can never be recognized as an authorized agent by the vault.
     */
    function invariant_UnauthorizedAgentNeverActive() public view {
        bytes32 fakeAgent = keccak256("fake_agent_hash_2026");
        assertEq(vault.isAgentAuthorizedFor(address(0x123), fakeAgent), false);
    }
}