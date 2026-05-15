// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;
import "forge-std/Test.sol";
import "../../contracts/AegisVault.sol";

contract Handler is Test {
    AegisVault public vault;
    uint256 public totalGhostBalance; 

    constructor(AegisVault _vault) {
        vault = _vault;
    }

    function deposit(uint256 amount) public {
        amount = bound(amount, 1 ether, 10 ether);
        vm.deal(address(this), amount);
        vault.deposit{value: amount}();
        totalGhostBalance += amount;
    }

    function withdraw(uint256 amount) public {
        uint256 bal = vault.balanceOf(address(this));
        if (bal == 0) return;
        amount = bound(amount, 1, bal);
        vault.withdraw(amount);
        totalGhostBalance -= amount;
    }
    receive() external payable {}
}