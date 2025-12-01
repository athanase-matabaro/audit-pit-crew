// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/**
 * @title VulnerableBank - Intentionally Vulnerable Contract for Testing
 * @notice This contract contains multiple security vulnerabilities for testing scanner tools
 */

interface IReceiver {
    function onReceive(bytes calldata data) external;
}

contract VulnerableBank {
    // ============ STATE VARIABLES ============
    
    mapping(address => uint256) public balances;
    address public owner;
    uint256 public totalDeposits;
    bool public locked;
    
    // ============ EVENTS ============
    
    event Deposit(address indexed user, uint256 amount);
    event Withdrawal(address indexed user, uint256 amount);
    event Transfer(address indexed from, address indexed to, uint256 amount);
    
    // ============ CONSTRUCTOR ============
    
    constructor() {
        owner = msg.sender;
    }
    
    // ============ VULNERABLE FUNCTIONS ============
    
    // VULNERABILITY 1: Reentrancy (Classic DAO vulnerability)
    // @notice UNSAFE: Calls external contract before updating state
    function withdrawUnsafe(uint256 amount) public {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        
        // VULNERABILITY: State update AFTER external call
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");
        
        // STATE CHANGE AFTER CALL - REENTRANCY POSSIBLE!
        balances[msg.sender] -= amount;
        totalDeposits -= amount;
    }
    
    // VULNERABILITY 2: Integer Overflow (Pre-0.8.0 style, though we're on 0.8)
    // @notice Unsafe arithmetic without proper checks
    function addFunds(uint256 amount) public {
        balances[msg.sender] = balances[msg.sender] + amount;
        totalDeposits = totalDeposits + amount;
        emit Deposit(msg.sender, amount);
    }
    
    // VULNERABILITY 3: Delegatecall to arbitrary address
    // @notice HIGH RISK: Delegatecall can execute arbitrary code in contract context
    function executeArbitraryCode(address target, bytes calldata data) public onlyOwner {
        // DANGEROUS: Delegatecall to untrusted address
        (bool success, ) = target.delegatecall(data);
        require(success, "Delegatecall failed");
    }
    
    // VULNERABILITY 4: Unchecked external call
    // @notice Return value not checked, can silently fail
    function transferFunds(address recipient, uint256 amount) public {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        
        // VULNERABILITY: External call return value ignored!
        recipient.call{value: amount}("");
        
        // State change happens even if call failed
        balances[msg.sender] -= amount;
        balances[recipient] += amount;
    }
    
    // VULNERABILITY 5: Unprotected state change
    // @notice No access control, anyone can call
    function emergencyWithdraw(address payable recipient) public {
        // VULNERABILITY: No onlyOwner check!
        recipient.transfer(address(this).balance);
    }
    
    // VULNERABILITY 6: Transaction order dependency (Front-running)
    // @notice Price can be influenced by tx ordering
    uint256 public exchangeRate = 100;
    
    function setExchangeRate(uint256 newRate) public {
        // VULNERABILITY: No access control, no rate limit
        exchangeRate = newRate;
    }
    
    // VULNERABILITY 7: Logic bug - wrong comparison
    // @notice Should be != but uses ==
    function withdrawAll() public {
        // VULNERABILITY: Logic error - condition always true/false
        if (balances[msg.sender] == 0) {
            revert("Balance is zero");
        }
        
        uint256 amount = balances[msg.sender];
        balances[msg.sender] = 0;
        
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");
    }
    
    // VULNERABILITY 8: Type confusion potential
    // @notice Mixing different numeric types unsafely
    function complexCalculation(uint8 a, uint256 b) public pure returns (uint256) {
        // VULNERABILITY: Implicit type conversion can cause issues
        uint256 result = uint256(a) + b;
        return result;
    }
    
    // VULNERABILITY 9: Missing input validation
    // @notice No validation on critical parameter
    function setOwner(address newOwner) public onlyOwner {
        // VULNERABILITY: No zero address check
        owner = newOwner;
    }
    
    // VULNERABILITY 10: Incorrect visibility
    // @notice Should be private but is internal + called externally
    function _criticalLogic(uint256 amount) internal {
        // Some critical logic
        balances[msg.sender] -= amount;
    }
    
    // VULNERABILITY 11: Use of tx.origin (Authorization bypass)
    // @notice tx.origin should never be used for auth
    function withdrawOnBehalf(address target, uint256 amount) public {
        // VULNERABILITY: Using tx.origin instead of msg.sender
        require(tx.origin == owner, "Only owner can call");
        
        balances[target] -= amount;
        (bool success, ) = target.call{value: amount}("");
        require(success, "Transfer failed");
    }
    
    // VULNERABILITY 12: Assert instead of require
    // @notice Assert consumes all gas when fails
    function debugWithdraw(uint256 amount) public {
        // VULNERABILITY: Using assert (consumes all gas on failure)
        assert(balances[msg.sender] >= amount);
        
        balances[msg.sender] -= amount;
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");
    }
    
    // ============ SAFE FUNCTION (For comparison) ============
    
    // SAFE: Follows checks-effects-interactions pattern
    function withdrawSafe(uint256 amount) public {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        require(amount > 0, "Amount must be positive");
        require(!locked, "Reentrancy guard triggered");
        
        locked = true;
        
        // SAFE: State changes BEFORE external calls
        balances[msg.sender] -= amount;
        totalDeposits -= amount;
        
        // SAFE: External call after state update
        (bool success, ) = msg.sender.call{value: amount}("");
        locked = false;
        
        require(success, "Transfer failed");
        emit Withdrawal(msg.sender, amount);
    }
    
    // ============ MODIFIERS ============
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner can call");
        _;
    }
    
    // ============ RECEIVE FUNCTION ============
    
    receive() external payable {
        balances[msg.sender] += msg.value;
        totalDeposits += msg.value;
        emit Deposit(msg.sender, msg.value);
    }
}
