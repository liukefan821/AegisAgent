// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @dev 定义 Automata 的官方验证接口
 */
interface IAutomataDcapVerifier {
    function verifyAttestation(bytes calldata quote) external returns (bool, bytes32);
}

/**
 * @title AegisVerifier
 * @notice 负责验证来自 TEE Agent 的硬件证明（Quote）
 */
contract AegisVerifier {
    IAutomataDcapVerifier public automataVerifier;

    event QuoteVerified(bytes32 indexed mrEnclave, bytes32 quoteDigest, bool success);

    constructor(address _automataVerifierAddress) {
        // 在 Sepolia 测试网上，这个地址是 Automata 官方提供的
        automataVerifier = IAutomataDcapVerifier(_automataVerifierAddress);
    }

    /**
     * @notice 验证 TEE 硬件证明并解析出镜像哈希
     * @param quote 来自 Phala TDX CVM 的原始 DCAP 证明
     * @param actionHash 交易内容的哈希值，确保证明与交易是一一对应的
     * @return success 验证是否通过
     * @return mrEnclave 解析出的 TEE 镜像哈希
     */
    function verify(bytes calldata quote, bytes32 actionHash) 
        external 
        returns (bool success, bytes32 mrEnclave) 
    {
        // 调用 Automata 的官方合约进行重度解析
        (success, mrEnclave) = automataVerifier.verifyAttestation(quote);
        
        // 注意：在完整版本中，我们需要额外校验 quote 里的 reportData 是否等于 actionHash
        // 这一步确保了 AI 生成的“防伪钢印”就是为了这笔交易生成的
        
        emit QuoteVerified(mrEnclave, keccak256(quote), success);
        return (success, mrEnclave);
    }
}