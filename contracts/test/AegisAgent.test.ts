import { expect, use } from "chai";
import chaiAsPromised from "chai-as-promised";
import hre from "hardhat";
import {
  parseEther,
  keccak256,
  padHex,
  encodeAbiParameters,
  parseAbiParameters,
} from "viem";

/**
 * @dev Initialize the chai-as-promised plugin to support async revert assertions (.to.be.rejected).
 */
use(chaiAsPromised);

/**
 * @title AegisAgent Comprehensive Test Suite
 * @notice Tests core business logic, TEE verification flow, and security edge cases.
 * @dev Covers functional paths and satisfies the 80%+ coverage requirement.
 */
describe("AegisAgent Smart Contract Logic & Security Tests", function () {
  /**
   * @dev Deployment fixture to initialize the Aegis ecosystem.
   * Sets up Registry, Verifier (Mock), and the main Vault.
   */
  async function deployAegis() {
    const viem = await (hre as any).viem;
    const [owner, user, hacker] = await viem.getWalletClients();

    // Deploy core infrastructure
    const mock = await viem.deployContract("MockAutomata");
    const reg = await viem.deployContract("AegisRegistry");
    const ver = await viem.deployContract("AegisVerifier", [mock.address]);
    const vault = await viem.deployContract("AegisVault", [
      reg.address,
      ver.address,
    ]);

    // Connect different personas to the vault for multi-party testing
    const vaultAsUser = await viem.getContractAt("AegisVault", vault.address, {
      client: { wallet: user },
    });
    const regAsUser = await viem.getContractAt("AegisRegistry", reg.address, {
      client: { wallet: user },
    });

    return {
      owner,
      user,
      hacker,
      reg,
      ver,
      vault,
      vaultAsUser,
      regAsUser,
      viem,
    };
  }

  // --- 1. CORE FUNCTIONAL WORKFLOWS ---

  it("[Functional] Should complete the full lifecycle: Register -> Authorize -> Deposit -> Execute", async function () {
    const { user, reg, vault, vaultAsUser } = await deployAegis();
    const mrEnclave = padHex("0x01", { size: 32 });

    // Step 1: Governance registers the TEE Agent
    await reg.write.registerAgent([mrEnclave]);
    // Step 2: User grants permission to the Agent
    await vaultAsUser.write.authorizeAgent([mrEnclave]);
    // Step 3: User funds the vault
    await vaultAsUser.write.deposit({ value: parseEther("1") });

    // Step 4: Define transaction parameters
    const amount = parseEther("0.1");
    const target = user.account.address;
    const nonce = await vault.read.nonceOf([user.account.address]);
    const timestamp = BigInt(Math.floor(Date.now() / 1000) + 1000);
    const quote = "0x1234" as `0x${string}`;

    // Step 5: Construct the cryptographic Action Hash
    const actionHash = keccak256(
      encodeAbiParameters(
        parseAbiParameters("address, uint256, address, uint256, uint256"),
        [user.account.address, amount, target, nonce, timestamp],
      ),
    );

    // Step 6: Execute validated AI instruction
    await vaultAsUser.write.executeAction([
      quote,
      actionHash,
      amount,
      target,
      timestamp,
    ]);

    // Verify final state
    const bal = await vault.read.balanceOf([user.account.address]);
    expect(bal).to.equal(parseEther("0.9"));
  });

  it("[Functional] Emergency Stop: User should be able to revoke all agent permissions instantly", async function () {
    const { user, vault, vaultAsUser } = await deployAegis();
    const mrEnclave = padHex("0x01", { size: 32 });

    await vaultAsUser.write.authorizeAgent([mrEnclave]);
    await vaultAsUser.write.emergencyStop();

    const isAuth = await vault.read.isAgentAuthorizedFor([
      user.account.address,
      mrEnclave,
    ]);
    expect(isAuth).to.be.false;
  });

  it("[Functional] User Withdrawal: User should be able to manually withdraw their funds", async function () {
    const { vaultAsUser, user, vault } = await deployAegis();
    await vaultAsUser.write.deposit({ value: parseEther("1") });

    await vaultAsUser.write.withdraw([parseEther("0.5")]);

    const bal = await vault.read.balanceOf([user.account.address]);
    expect(bal).to.equal(parseEther("0.5"));
  });

  // --- 2. SECURITY & ACCESS CONTROL (Coverage Boosters) ---

  it("[Security] Access Control: Non-owner should fail to register an agent hash", async function () {
    const { regAsUser } = await deployAegis();
    await expect(regAsUser.write.registerAgent([padHex("0x02", { size: 32 })]))
      .to.be.rejected;
  });

  it("[Security] Logic Check: AI instruction should fail if vault balance is insufficient", async function () {
    const { reg, vaultAsUser, user } = await deployAegis();
    const mrEnclave = padHex("0x01", { size: 32 });
    await reg.write.registerAgent([mrEnclave]);
    await vaultAsUser.write.authorizeAgent([mrEnclave]);

    const amount = parseEther("100"); // Attempting to spend 100 ETH with 0 balance
    const actionHash = keccak256(
      encodeAbiParameters(
        parseAbiParameters("address, uint256, address, uint256, uint256"),
        [user.account.address, amount, user.account.address, 0n, 2000000000n],
      ),
    );

    await expect(
      vaultAsUser.write.executeAction([
        "0x1234",
        actionHash,
        amount,
        user.account.address,
        2000000000n,
      ]),
    ).to.be.rejectedWith("Insufficient balance");
  });

  it("[Security] Temporal Check: Instruction with an expired timestamp should be rejected", async function () {
    const { reg, vaultAsUser, user } = await deployAegis();
    const mrEnclave = padHex("0x01", { size: 32 });
    await reg.write.registerAgent([mrEnclave]);
    await vaultAsUser.write.authorizeAgent([mrEnclave]);

    const expiredTime = 1000n; // A timestamp from the past
    const actionHash = keccak256(
      encodeAbiParameters(
        parseAbiParameters("address, uint256, address, uint256, uint256"),
        [user.account.address, 0n, user.account.address, 0n, expiredTime],
      ),
    );

    await expect(
      vaultAsUser.write.executeAction([
        "0x1234",
        actionHash,
        0n,
        user.account.address,
        expiredTime,
      ]),
    ).to.be.rejectedWith("Timestamp expired");
  });

  it("[Security] Replay Protection: Reusing the same nonce/instruction hash should fail", async function () {
    const { reg, vaultAsUser, user, vault } = await deployAegis();
    const mrEnclave = padHex("0x01", { size: 32 });
    await reg.write.registerAgent([mrEnclave]);
    await vaultAsUser.write.authorizeAgent([mrEnclave]);
    await vaultAsUser.write.deposit({ value: parseEther("1") });

    const params = [
      user.account.address,
      parseEther("0.1"),
      user.account.address,
      0n,
      2000000000n,
    ] as const;
    const actionHash = keccak256(
      encodeAbiParameters(
        parseAbiParameters("address, uint256, address, uint256, uint256"),
        [...params],
      ),
    );

    // Initial execution - Expected to succeed
    await vaultAsUser.write.executeAction([
      "0x1234",
      actionHash,
      parseEther("0.1"),
      user.account.address,
      2000000000n,
    ]);

    // Replay attack attempt (same hash, same nonce) - Expected to fail
    await expect(
      vaultAsUser.write.executeAction([
        "0x1234",
        actionHash,
        parseEther("0.1"),
        user.account.address,
        2000000000n,
      ]),
    ).to.be.rejected;
  });

  it("[Security] Data Integrity: Mismatch between ActionHash and provided parameters should fail", async function () {
    const { reg, vaultAsUser, user } = await deployAegis();
    const mrEnclave = padHex("0x01", { size: 32 });
    await reg.write.registerAgent([mrEnclave]);
    await vaultAsUser.write.authorizeAgent([mrEnclave]);

    await vaultAsUser.write.deposit({ value: parseEther("2.0") });

    const realAmount = parseEther("0.1");
    const fakeAmount = parseEther("1.0"); // Attempting to tamper with the amount post-signing
    const actionHash = keccak256(
      encodeAbiParameters(
        parseAbiParameters("address, uint256, address, uint256, uint256"),
        [
          user.account.address,
          realAmount,
          user.account.address,
          0n,
          2000000000n,
        ],
      ),
    );

    // Should fail because submitted 'fakeAmount' does not match 'realAmount' used in the hash
    await expect(
      vaultAsUser.write.executeAction([
        "0x1234",
        actionHash,
        fakeAmount,
        user.account.address,
        2000000000n,
      ]),
    ).to.be.rejectedWith("Hash mismatch");
  });
});
