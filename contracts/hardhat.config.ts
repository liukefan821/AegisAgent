import type { HardhatUserConfig } from "hardhat/config";
import "@nomicfoundation/hardhat-toolbox-viem";

const config: HardhatUserConfig = {
  solidity: "0.8.28",
  gasReporter: {
    enabled: true, // 必须设为 true 才会显示报告
    currency: "USD", // 可选：将 Gas 换算成美元
    gasPrice: 20, // 可选：设置平均 Gas 价格 (Gwei)
  },
};

export default config;
