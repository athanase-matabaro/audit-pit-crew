// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract VulnerableBank {
    mapping(address => uint256) public balances;

    function deposit() public payable {
        balances[msg.sender] += msg.value;
    }

    // 🚨 BUG: Reentrancy here (sending ETH before updating balance)
    function withdraw() public {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "No funds");

        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");

        balances[msg.sender] = 0;
    }audit-pit-crew-scanner.
}