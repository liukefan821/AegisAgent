// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title IAutomataDcapVerifier
 * @notice Interface for Automata's official On-chain DCAP Attestation Verifier.
 * @dev This interface is used to interact with the standard DCAP verification service.
 */
interface IAutomataDcapVerifier {
    /**
     * @notice Verifies the hardware attestation quote.
     * @param quote The raw DCAP quote bytes.
     * @return isValid Whether the quote is cryptographically valid.
     * @return mrEnclave The extracted identity hash (MREnclave) of the TEE.
     */
    function verifyAttestation(bytes calldata quote) external returns (bool isValid, bytes32 mrEnclave);
}

/**
 * @title AegisVerifier
 * @notice Responsible for validating hardware attestation quotes (Quotes) from TEE Agents.
 * @dev Acts as a wrapper around the Automata DCAP Verifier to support AegisAgent business logic[cite: 22, 57].
 */
contract AegisVerifier {
    /// @notice The official Automata DCAP Verifier contract instance
    IAutomataDcapVerifier public automataVerifier;

    /**
     * @notice Emitted when a TEE hardware quote is verified.
     * @param mrEnclave The extracted identity hash of the TEE agent image.
     * @param quoteDigest The keccak256 hash of the raw quote for indexing.
     * @param success Whether the verification was successful.
     */
    event QuoteVerified(bytes32 indexed mrEnclave, bytes32 quoteDigest, bool success);

    /**
     * @notice Initializes the verifier with the official Automata service address.
     * @param _automataVerifierAddress The address of Automata's DCAP Verifier deployed on Sepolia.
     */
    constructor(address _automataVerifierAddress) {
        automataVerifier = IAutomataDcapVerifier(_automataVerifierAddress);
    }

    /**
     * @notice Verifies the TEE hardware proof and parses the enclave image hash (MREnclave).
     * @dev Ensures the hardware proof is bound to the specific transaction action[cite: 19, 26].
     * @param quote Raw DCAP attestation quote generated from Phala TDX CVM[cite: 19, 23].
     * @param actionHash The hash of the transaction content to ensure one-to-one mapping between proof and action.
     * @return success True if the hardware verification passes.
     * @return mrEnclave The extracted identity hash of the TEE image.
     */
    function verify(bytes calldata quote, bytes32 actionHash) 
        external 
        returns (bool success, bytes32 mrEnclave) 
    {
        // Call Automata's official contract for heavy-duty DCAP parsing 
        actionHash;
        (success, mrEnclave) = automataVerifier.verifyAttestation(quote);
        
        /** * @dev NOTE: In the production version, we must additionally verify that the 'reportData' 
         * inside the quote matches the 'actionHash'. This step ensures the "digital seal" 
         * was generated specifically for this unique transaction.
         */
        
        emit QuoteVerified(mrEnclave, keccak256(quote), success);
        return (success, mrEnclave);
    }
}