// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @dev Interface for the AegisRegistry contract to verify if an agent is whitelisted.
 */
interface IAegisRegistry {
    function isRegistered(bytes32 mrEnclave) external view returns (bool);
}

/**
 * @dev Interface for the AegisVerifier contract to validate TEE hardware attestations.
 */
interface IAegisVerifier {
    function verify(bytes calldata quote, bytes32 actionHash) external returns (bool success, bytes32 mrEnclave);
}

/**
 * @title AegisVault
 * @notice A secure custody vault where funds can only be moved via TEE-verified AI instructions.
 * @dev This contract manages user balances, agent authorizations, and executes verified actions.
 *      Uses a reentrancy lock to prevent cross-function reentrancy via low-level calls.
 */
contract AegisVault {
    /// @notice Reference to the Agent Registry contract
    IAegisRegistry public registry;
    /// @notice Reference to the TEE Attestation Verifier contract
    IAegisVerifier public verifier;

    mapping(address => uint256) private _balances;
    mapping(address => mapping(bytes32 => bool)) private _authorizations;
    mapping(address => uint256) private _lastActionTimestamp;
    mapping(address => uint256) private _nonces;
    mapping(address => bool) private _emergencyStopped;

    uint256 private constant _NOT_ENTERED = 1;
    uint256 private constant _ENTERED = 2;
    uint256 private _status;

    /// @dev Emitted when a user deposits ETH into the vault.
    event Deposited(address indexed user, uint256 amount);
    /// @dev Emitted when a user withdraws ETH from the vault.
    event Withdrawn(address indexed user, uint256 amount);
    /// @dev Emitted when a user authorizes a specific TEE agent (via mrEnclave).
    event AgentAuthorized(address indexed user, bytes32 indexed mrEnclave);
    /// @dev Emitted when a user triggers the emergency stop to freeze all agent activities.
    event EmergencyStopped(address indexed user);
    /// @dev Emitted when a TEE agent successfully executes a verified action.
    event ActionExecuted(address indexed user, bytes32 indexed mrEnclave, bytes32 quoteDigest, uint256 amount, uint256 timestamp);

    /// @dev Prevents reentrant calls to state-changing functions.
    modifier nonReentrant() {
        require(_status != _ENTERED, "ReentrancyGuard: reentrant call");
        _status = _ENTERED;
        _;
        _status = _NOT_ENTERED;
    }

    /**
     * @dev Initializes the vault with the addresses of the Registry and Verifier.
     * @param _registryAddress Address of the AegisRegistry contract.
     * @param _verifierAddress Address of the AegisVerifier contract.
     */
    constructor(address _registryAddress, address _verifierAddress) {
        registry = IAegisRegistry(_registryAddress);
        verifier = IAegisVerifier(_verifierAddress);
        _status = _NOT_ENTERED;
    }

    // --- Read-Only Functions ---

    /**
     * @notice Returns the ETH balance of a specific user in the vault.
     * @param user The address of the user.
     * @return The user's balance in wei.
     */
    function balanceOf(address user) external view returns (uint256) {
        return _balances[user];
    }

    /**
     * @notice Checks if a specific agent is authorized to manage a user's funds.
     * @dev An agent is only authorized if the user has granted permission and has NOT triggered an emergency stop.
     * @param user The address of the user.
     * @param mrEnclave The identity hash of the TEE agent image.
     * @return True if the agent is currently authorized.
     */
    function isAgentAuthorizedFor(address user, bytes32 mrEnclave) external view returns (bool) {
        return _authorizations[user][mrEnclave] && !_emergencyStopped[user];
    }

    /**
     * @notice Returns the current nonce for a user to prevent replay attacks.
     * @param user The address of the user.
     * @return The current nonce value.
     */
    function nonceOf(address user) external view returns (uint256) {
        return _nonces[user];
    }

    // --- User Operation Functions ---

    /**
     * @notice Allows users to deposit ETH into their vault account.
     */
    function deposit() external payable {
        _balances[msg.sender] += msg.value;
        emit Deposited(msg.sender, msg.value);
    }

    /**
     * @notice Allows users to manually withdraw their funds from the vault.
     * @dev Uses call instead of transfer to avoid the 2300 gas stipend limitation.
     * @param amount The amount of ETH to withdraw in wei.
     */
    function withdraw(uint256 amount) external nonReentrant {
        require(_balances[msg.sender] >= amount, "Insufficient balance");
        _balances[msg.sender] -= amount;

        (bool success, ) = payable(msg.sender).call{value: amount}("");
        require(success, "ETH transfer failed");

        emit Withdrawn(msg.sender, amount);
    }

    /**
     * @notice Authorizes a specific TEE agent to act on behalf of the user.
     * @param mrEnclave The identity hash of the TEE agent image.
     */
    function authorizeAgent(bytes32 mrEnclave) external {
        _authorizations[msg.sender][mrEnclave] = true;
        emit AgentAuthorized(msg.sender, mrEnclave);
    }

    /**
     * @notice Immediately revokes all agent authorizations for the user.
     * @dev This is a security feature to protect funds if an agent is suspected of malicious behavior.
     */
    function emergencyStop() external {
        _emergencyStopped[msg.sender] = true;
        emit EmergencyStopped(msg.sender);
    }

    /**
     * @notice Executes a transaction decided by a verified TEE Agent autonomously.
     * @dev Validates the hardware quote, checks registration/authorization, and verifies the action hash.
     *      Follows checks-effects-interactions pattern and uses nonReentrant guard.
     * @param user The address of the user whose funds are being managed.
     * @param quote The raw hardware attestation quote provided by the TEE.
     * @param actionHash The cryptographic hash of the intended action (user, amount, target, nonce, timestamp).
     * @param amount The amount of ETH to be transferred.
     * @param target The recipient address of the transfer.
     * @param timestamp The expiration deadline for this specific instruction.
     */
    function executeAction(
        address user,
        bytes calldata quote,
        bytes32 actionHash,
        uint256 amount,
        address target,
        uint256 timestamp
    ) external nonReentrant {
        // 1. Core security checks
        require(timestamp > block.timestamp, "Timestamp expired");
        require(!_emergencyStopped[user], "Emergency stop active");
        require(_balances[user] >= amount, "Insufficient balance");

        // 2. Hardware proof verification
        (bool ok, bytes32 mrEnclave) = verifier.verify(quote, actionHash);
        require(ok, "Hardware verification failed");

        // 3. Registry and Authorization checks
        require(registry.isRegistered(mrEnclave), "Agent image not registered");
        require(_authorizations[user][mrEnclave], "User has not authorized this agent");

        // 4. Reconstruct and verify hash to prevent tampering
        bytes32 expectedHash = keccak256(abi.encode(user, amount, target, _nonces[user], timestamp));
        require(actionHash == expectedHash, "Hash mismatch");

        // 5. Effects: update state before external call (checks-effects-interactions)
        _balances[user] -= amount;
        _nonces[user] += 1;
        _lastActionTimestamp[user] = block.timestamp;

        // 6. Interaction: external call after all state updates
        (bool success, ) = payable(target).call{value: amount}("");
        require(success, "Transfer failed");

        emit ActionExecuted(user, mrEnclave, keccak256(quote), amount, block.timestamp);
    }
}