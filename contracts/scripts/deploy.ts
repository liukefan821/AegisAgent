import hre from "hardhat";

async function main() {
  console.log("Starting deployment on Sepolia...");

  // 1. 获取 Viem 的钱包客户端
  const walletClients = await hre.viem.getWalletClients();
  const deployer = walletClients[0];
  console.log(
    "Deploying contracts with the account:",
    deployer.account.address,
  );

  // 2. 部署 AegisRegistry
  const registry = await hre.viem.deployContract("AegisRegistry");
  console.log("AegisRegistry deployed to:", registry.address);

  // 3. 部署 MockAutomata
  const mockAutomata = await hre.viem.deployContract("MockAutomata");
  console.log("MockAutomata deployed to:", mockAutomata.address);

  // 4. 部署 AegisVerifier
  const verifier = await hre.viem.deployContract("AegisVerifier", [
    mockAutomata.address,
  ]);
  console.log("AegisVerifier deployed to:", verifier.address);

  // 5. 部署 AegisVault
  const vault = await hre.viem.deployContract("AegisVault", [
    registry.address,
    verifier.address,
  ]);
  console.log("AegisVault deployed to:", vault.address);

  // 6. 注册一个测试用的 TEE Image Hash (mrEnclave)
  console.log("Registering a mock TEE image...");
  const mockMrEnclave =
    "0x0000000000000000000000000000000000000000000000000000000000000001";
  await registry.write.registerAgent([mockMrEnclave]);
  console.log("Mock TEE image registered!");

  console.log("Deployment Complete! ");
  console.log("--------------------------------------------------");
  console.log(`Registry: ${registry.address}`);
  console.log(`Verifier: ${verifier.address}`);
  console.log(`Vault:    ${vault.address}`);
  console.log("--------------------------------------------------");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
