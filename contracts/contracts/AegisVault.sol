// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IAegisRegistry {
    function isRegistered(bytes32 mrEnclave) external view returns (bool);
}

interface IAegisVerifier {
    function verify(bytes calldata quote, bytes32 actionHash) external returns (bool success, bytes32 mrEnclave);
}

/**
 * @title AegisVault
 * @notice 用户资金托管金库，只有通过硬件验证的 AI 指令才能动用资金
 */
contract AegisVault {
    IAegisRegistry public registry;
    IAegisVerifier public verifier;

    mapping(address => uint256) private _balances;
    mapping(address => mapping(bytes32 => bool)) private _authorizations;
    mapping(address => uint256) private _lastActionTimestamp;
    mapping(address => uint256) private _nonces;
    mapping(address => bool) private _emergencyStopped;

    event Deposited(address indexed user, uint256 amount);
    event Withdrawn(address indexed user, uint256 amount);
    event AgentAuthorized(address indexed user, bytes32 indexed mrEnclave);
    event EmergencyStopped(address indexed user);
    event ActionExecuted(address indexed user, bytes32 indexed mrEnclave, bytes32 quoteDigest, uint256 amount, uint256 timestamp);

    constructor(address _registryAddress, address _verifierAddress) {
        registry = IAegisRegistry(_registryAddress);
        verifier = IAegisVerifier(_verifierAddress);
    }

    // --- 只读函数 ---

    function balanceOf(address user) external view returns (uint256) {
        return _balances[user];
    }

    function isAgentAuthorizedFor(address user, bytes32 mrEnclave) external view returns (bool) {
        return _authorizations[user][mrEnclave] && !_emergencyStopped[user];
    }

    function nonceOf(address user) external view returns (uint256) {
        return _nonces[user];
    }

    // --- 用户操作函数 ---

    function deposit() external payable {
        _balances[msg.sender] += msg.value;
        emit Deposited(msg.sender, msg.value);
    }

    function withdraw(uint256 amount) external {
        require(_balances[msg.sender] >= amount, "Insufficient balance");
        _balances[msg.sender] -= amount;
        payable(msg.sender).transfer(amount);
        emit Withdrawn(msg.sender, amount);
    }

    function authorizeAgent(bytes32 mrEnclave) external {
        _authorizations[msg.sender][mrEnclave] = true;
        emit AgentAuthorized(msg.sender, mrEnclave);
    }

    function emergencyStop() external {
        _emergencyStopped[msg.sender] = true;
        emit EmergencyStopped(msg.sender);
    }

    /**
     * @notice 执行由 TEE Agent 决定的交易
     * @dev 已经修复了 timestamp 参数 Bug，与 TEE 端的 action_hash 生成算法完全对齐
     */
    function executeAction(
        bytes calldata quote,
        bytes32 actionHash,
        uint256 amount,
        address target,
        uint256 timestamp  // <--- 已补全此关键参数
    ) external {
        require(!_emergencyStopped[msg.sender], "Emergency stop active");
        require(_balances[msg.sender] >= amount, "Vault balance too low");

        // 1. 验证硬件证明真伪
        (bool ok, bytes32 mrEnclave) = verifier.verify(quote, actionHash);
        require(ok, "Hardware verification failed");

        // 2. 检查 AI 镜像是否在官方白名单中
        require(registry.isRegistered(mrEnclave), "Agent image not registered");

        // 3. 检查用户是否授权过这个 AI
        require(_authorizations[msg.sender][mrEnclave], "User has not authorized this agent");

        // 4. 重构哈希并核对，防止 AI 篡改交易内容或时间
        bytes32 expectedHash = keccak256(abi.encode(msg.sender, amount, target, _nonces[msg.sender], timestamp));
        require(actionHash == expectedHash, "Tamper detected: Action hash mismatch");

        // 5. 执行具体业务逻辑：扣款、增加 nonce、更新时间戳并转账
        _balances[msg.sender] -= amount;
        _nonces[msg.sender] += 1;
        _lastActionTimestamp[msg.sender] = block.timestamp;
        
        (bool success, ) = target.call{value: amount}("");
        require(success, "Contract execution failed");

        emit ActionExecuted(msg.sender, mrEnclave, keccak256(quote), amount, block.timestamp);
    }
}