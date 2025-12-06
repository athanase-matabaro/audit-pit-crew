"""
Remediation patterns for security detectors.

This module maps detector IDs (from Slither) and SWC IDs (from Mythril)
to remediation information including:
- A short summary of the fix
- Code snippets showing the recommended pattern
- Reference links for further reading
- Risk level context

IMPORTANT: These are "Educational Snippets" - standard patterns that developers
should adapt to their specific context. They are NOT automatic patches.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class RemediationPattern:
    """Represents a remediation suggestion for a security issue."""
    
    detector_id: str  # Slither detector ID or SWC ID
    title: str  # Human-readable title
    summary: str  # One-line fix summary
    explanation: str  # Detailed explanation of the vulnerability
    fix_snippet: str  # Code snippet showing the fix pattern
    references: list  # URLs for further reading
    risk_context: str  # Additional context about the risk
    applies_to: str = "solidity"  # Language/context this applies to


# =============================================================================
# SLITHER DETECTOR PATTERNS
# Top detectors ordered by frequency and severity
# =============================================================================

SLITHER_PATTERNS: Dict[str, RemediationPattern] = {
    # ---------------------------------------------------------------------
    # HIGH SEVERITY
    # ---------------------------------------------------------------------
    "reentrancy-eth": RemediationPattern(
        detector_id="reentrancy-eth",
        title="Reentrancy Vulnerability (ETH)",
        summary="Use the Checks-Effects-Interactions pattern and/or ReentrancyGuard",
        explanation="""
A reentrancy vulnerability allows an attacker to recursively call back into 
your contract before the first execution completes. This can drain funds 
if state changes happen after external calls.

The "Checks-Effects-Interactions" pattern requires:
1. CHECK all conditions first
2. Make all state changes (EFFECTS)
3. Only then make external calls (INTERACTIONS)
""",
        fix_snippet="""
// ❌ VULNERABLE: State change after external call
function withdraw() external {
    uint256 amount = balances[msg.sender];
    (bool success, ) = msg.sender.call{value: amount}("");
    require(success, "Transfer failed");
    balances[msg.sender] = 0;  // State change AFTER call - vulnerable!
}

// ✅ FIXED: Using Checks-Effects-Interactions pattern
function withdraw() external {
    uint256 amount = balances[msg.sender];
    require(amount > 0, "No balance");  // CHECK
    
    balances[msg.sender] = 0;  // EFFECT - state change BEFORE call
    
    (bool success, ) = msg.sender.call{value: amount}("");  // INTERACTION
    require(success, "Transfer failed");
}

// ✅ ALTERNATIVE: Using OpenZeppelin ReentrancyGuard
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

contract MyContract is ReentrancyGuard {
    function withdraw() external nonReentrant {
        uint256 amount = balances[msg.sender];
        balances[msg.sender] = 0;
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");
    }
}
""",
        references=[
            "https://docs.openzeppelin.com/contracts/4.x/api/security#ReentrancyGuard",
            "https://swcregistry.io/docs/SWC-107",
            "https://consensys.github.io/smart-contract-best-practices/attacks/reentrancy/",
        ],
        risk_context="Critical in contracts handling ETH/tokens. Can lead to complete fund drainage.",
    ),
    
    "reentrancy-no-eth": RemediationPattern(
        detector_id="reentrancy-no-eth",
        title="Reentrancy Vulnerability (No ETH)",
        summary="Apply Checks-Effects-Interactions pattern even for non-ETH external calls",
        explanation="""
Even when not transferring ETH, reentrancy can occur through external contract
calls that call back into your contract. This can manipulate state in unexpected ways.
""",
        fix_snippet="""
// ❌ VULNERABLE: State change after external call
function transferTokens(address to, uint256 amount) external {
    token.transfer(to, amount);  // External call
    userBalances[msg.sender] -= amount;  // State change after
}

// ✅ FIXED: State change before external call
function transferTokens(address to, uint256 amount) external {
    require(userBalances[msg.sender] >= amount, "Insufficient balance");
    userBalances[msg.sender] -= amount;  // State change BEFORE
    token.transfer(to, amount);  // External call AFTER
}
""",
        references=[
            "https://swcregistry.io/docs/SWC-107",
            "https://docs.openzeppelin.com/contracts/4.x/api/security#ReentrancyGuard",
        ],
        risk_context="Can lead to state manipulation and logic bypass.",
    ),
    
    "arbitrary-send-eth": RemediationPattern(
        detector_id="arbitrary-send-eth",
        title="Arbitrary ETH Send",
        summary="Validate recipient address and use access control",
        explanation="""
Functions that send ETH to arbitrary addresses controlled by user input can be
exploited to drain contract funds. Always validate recipients and use proper
access control.
""",
        fix_snippet="""
// ❌ VULNERABLE: Anyone can specify any recipient
function sendFunds(address payable to, uint256 amount) external {
    to.transfer(amount);
}

// ✅ FIXED: Whitelist recipients or restrict to owner
mapping(address => bool) public approvedRecipients;

function sendFunds(address payable to, uint256 amount) external onlyOwner {
    require(approvedRecipients[to], "Recipient not approved");
    require(amount <= maxWithdrawal, "Amount exceeds limit");
    to.transfer(amount);
    emit FundsSent(to, amount);
}
""",
        references=[
            "https://swcregistry.io/docs/SWC-105",
        ],
        risk_context="Can result in complete loss of contract funds.",
    ),
    
    "suicidal": RemediationPattern(
        detector_id="suicidal",
        title="Unprotected Selfdestruct",
        summary="Add strict access control to selfdestruct operations",
        explanation="""
An unprotected selfdestruct allows anyone to destroy the contract and send
all its ETH to an arbitrary address. This should always be protected with
strict access control.
""",
        fix_snippet="""
// ❌ VULNERABLE: Anyone can destroy the contract
function destroy() external {
    selfdestruct(payable(msg.sender));
}

// ✅ FIXED: Only owner with timelock
address public owner;
uint256 public destructionRequestTime;
uint256 constant TIMELOCK = 7 days;

function requestDestruction() external onlyOwner {
    destructionRequestTime = block.timestamp;
    emit DestructionRequested(block.timestamp);
}

function executeDestruction(address payable recipient) external onlyOwner {
    require(destructionRequestTime > 0, "Not requested");
    require(block.timestamp >= destructionRequestTime + TIMELOCK, "Timelock active");
    emit ContractDestroyed(recipient);
    selfdestruct(recipient);
}
""",
        references=[
            "https://swcregistry.io/docs/SWC-106",
        ],
        risk_context="Results in permanent contract destruction and fund loss.",
    ),
    
    "controlled-delegatecall": RemediationPattern(
        detector_id="controlled-delegatecall",
        title="Controlled Delegatecall",
        summary="Never delegatecall to user-controlled addresses",
        explanation="""
Delegatecall executes code in another contract while maintaining the calling
contract's context (storage, msg.sender, etc.). If the target is user-controlled,
attackers can execute arbitrary code and take over your contract.
""",
        fix_snippet="""
// ❌ VULNERABLE: User controls delegatecall target
function execute(address target, bytes calldata data) external {
    target.delegatecall(data);  // Attacker can point to malicious contract
}

// ✅ FIXED: Whitelist allowed implementations
mapping(address => bool) public trustedImplementations;

function execute(address target, bytes calldata data) external onlyOwner {
    require(trustedImplementations[target], "Untrusted implementation");
    (bool success, ) = target.delegatecall(data);
    require(success, "Delegatecall failed");
}

// ✅ BETTER: Use OpenZeppelin's Proxy patterns
// See: https://docs.openzeppelin.com/contracts/4.x/api/proxy
""",
        references=[
            "https://swcregistry.io/docs/SWC-112",
            "https://docs.openzeppelin.com/contracts/4.x/api/proxy",
        ],
        risk_context="Can lead to complete contract takeover.",
    ),
    
    # ---------------------------------------------------------------------
    # MEDIUM SEVERITY
    # ---------------------------------------------------------------------
    "unchecked-transfer": RemediationPattern(
        detector_id="unchecked-transfer",
        title="Unchecked ERC20 Transfer",
        summary="Use SafeERC20 or check return values of transfer/transferFrom",
        explanation="""
Some ERC20 tokens don't follow the standard and return false instead of
reverting on failure. If you don't check the return value, transfers can
silently fail while your contract continues executing.
""",
        fix_snippet="""
// ❌ VULNERABLE: Not checking return value
function deposit(uint256 amount) external {
    token.transferFrom(msg.sender, address(this), amount);
    balances[msg.sender] += amount;  // Added even if transfer failed!
}

// ✅ FIXED: Check return value
function deposit(uint256 amount) external {
    bool success = token.transferFrom(msg.sender, address(this), amount);
    require(success, "Transfer failed");
    balances[msg.sender] += amount;
}

// ✅ BETTER: Use OpenZeppelin SafeERC20
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

contract MyContract {
    using SafeERC20 for IERC20;
    
    function deposit(uint256 amount) external {
        token.safeTransferFrom(msg.sender, address(this), amount);
        balances[msg.sender] += amount;
    }
}
""",
        references=[
            "https://docs.openzeppelin.com/contracts/4.x/api/token/erc20#SafeERC20",
            "https://consensys.github.io/smart-contract-best-practices/development-recommendations/token-specific/erc20/",
        ],
        risk_context="Can lead to accounting errors and fund loss.",
    ),
    
    "unchecked-lowlevel": RemediationPattern(
        detector_id="unchecked-lowlevel",
        title="Unchecked Low-Level Call",
        summary="Always check the success return value of low-level calls",
        explanation="""
Low-level calls (call, delegatecall, staticcall) return a boolean indicating
success. If you don't check it, failed calls will silently continue execution.
""",
        fix_snippet="""
// ❌ VULNERABLE: Not checking call success
function sendEther(address to, uint256 amount) external {
    to.call{value: amount}("");  // May fail silently
}

// ✅ FIXED: Check return value
function sendEther(address to, uint256 amount) external {
    (bool success, ) = to.call{value: amount}("");
    require(success, "ETH transfer failed");
}

// ✅ ALTERNATIVE: Use Address library
import "@openzeppelin/contracts/utils/Address.sol";

contract MyContract {
    using Address for address payable;
    
    function sendEther(address payable to, uint256 amount) external {
        to.sendValue(amount);  // Reverts on failure
    }
}
""",
        references=[
            "https://swcregistry.io/docs/SWC-104",
            "https://docs.openzeppelin.com/contracts/4.x/api/utils#Address",
        ],
        risk_context="Can lead to silent failures and inconsistent state.",
    ),
    
    "missing-zero-check": RemediationPattern(
        detector_id="missing-zero-check",
        title="Missing Zero Address Check",
        summary="Validate that address parameters are not the zero address",
        explanation="""
Setting critical addresses (owner, admin, token) to the zero address can
brick the contract or lock funds permanently. Always validate address inputs.
""",
        fix_snippet="""
// ❌ VULNERABLE: No validation
function setOwner(address newOwner) external onlyOwner {
    owner = newOwner;  // Could be set to address(0)!
}

// ✅ FIXED: Validate address
function setOwner(address newOwner) external onlyOwner {
    require(newOwner != address(0), "Invalid address: zero address");
    address oldOwner = owner;
    owner = newOwner;
    emit OwnershipTransferred(oldOwner, newOwner);
}

// ✅ BETTER: Use OpenZeppelin Ownable2Step for safe ownership transfer
import "@openzeppelin/contracts/access/Ownable2Step.sol";
""",
        references=[
            "https://docs.openzeppelin.com/contracts/4.x/api/access#Ownable2Step",
        ],
        risk_context="Can permanently lock contract functionality.",
    ),
    
    "locked-ether": RemediationPattern(
        detector_id="locked-ether",
        title="Locked Ether",
        summary="Add a withdraw function for contracts that receive ETH",
        explanation="""
Contracts that can receive ETH (via receive/fallback or payable functions)
but have no way to withdraw it will permanently lock those funds.
""",
        fix_snippet="""
// ❌ VULNERABLE: Can receive ETH but can't withdraw
contract Vault {
    receive() external payable {}
    // No way to get ETH out!
}

// ✅ FIXED: Add withdraw function
contract Vault {
    address public owner;
    
    receive() external payable {}
    
    function withdraw(uint256 amount) external onlyOwner {
        require(amount <= address(this).balance, "Insufficient balance");
        (bool success, ) = owner.call{value: amount}("");
        require(success, "Withdrawal failed");
    }
    
    function emergencyWithdraw() external onlyOwner {
        (bool success, ) = owner.call{value: address(this).balance}("");
        require(success, "Emergency withdrawal failed");
    }
}
""",
        references=[
            "https://consensys.github.io/smart-contract-best-practices/development-recommendations/general/external-calls/",
        ],
        risk_context="Permanently locks ETH with no recovery mechanism.",
    ),
    
    "tx-origin": RemediationPattern(
        detector_id="tx-origin",
        title="Dangerous tx.origin Usage",
        summary="Use msg.sender instead of tx.origin for authentication",
        explanation="""
tx.origin refers to the original external account that started the transaction.
Using it for authentication is dangerous because if a user interacts with a
malicious contract, that contract can call your contract and tx.origin will
still be the user's address.
""",
        fix_snippet="""
// ❌ VULNERABLE: Using tx.origin for auth
function withdraw() external {
    require(tx.origin == owner, "Not owner");  // Phishing vulnerable!
    // ...
}

// ✅ FIXED: Use msg.sender
function withdraw() external {
    require(msg.sender == owner, "Not owner");
    // ...
}

// ✅ BETTER: Use OpenZeppelin Ownable
import "@openzeppelin/contracts/access/Ownable.sol";

contract MyContract is Ownable {
    function withdraw() external onlyOwner {
        // ...
    }
}
""",
        references=[
            "https://swcregistry.io/docs/SWC-115",
            "https://consensys.github.io/smart-contract-best-practices/development-recommendations/solidity-specific/tx-origin/",
        ],
        risk_context="Enables phishing attacks where users lose funds.",
    ),
    
    "uninitialized-state": RemediationPattern(
        detector_id="uninitialized-state",
        title="Uninitialized State Variable",
        summary="Initialize state variables in the constructor or at declaration",
        explanation="""
Uninitialized state variables have default values (0, false, address(0)).
Relying on these defaults can lead to unexpected behavior, especially for
critical variables like ownership or configuration.
""",
        fix_snippet="""
// ❌ VULNERABLE: Critical state not initialized
contract Token {
    address owner;  // Defaults to address(0)
    uint256 totalSupply;  // Defaults to 0
    
    function mint(uint256 amount) external {
        require(msg.sender == owner);  // Will always fail!
        totalSupply += amount;
    }
}

// ✅ FIXED: Initialize in constructor
contract Token {
    address public owner;
    uint256 public totalSupply;
    
    constructor(uint256 _initialSupply) {
        owner = msg.sender;  // Explicitly set
        totalSupply = _initialSupply;
    }
}

// ✅ ALTERNATIVE: Initialize at declaration
contract Token {
    address public owner = msg.sender;  // Set at deployment
    uint256 public constant INITIAL_SUPPLY = 1_000_000 * 10**18;
}
""",
        references=[
            "https://swcregistry.io/docs/SWC-109",
        ],
        risk_context="Can lead to broken access control or incorrect logic.",
    ),
    
    "unused-return": RemediationPattern(
        detector_id="unused-return",
        title="Unused Return Value",
        summary="Handle or explicitly ignore return values from external calls",
        explanation="""
Ignoring return values from functions can hide failures or missed data.
This is especially critical for ERC20 operations and external calls.
""",
        fix_snippet="""
// ❌ VULNERABLE: Return value ignored
function approveToken(address spender, uint256 amount) external {
    token.approve(spender, amount);  // Returns bool, ignored!
}

// ✅ FIXED: Check return value
function approveToken(address spender, uint256 amount) external {
    bool success = token.approve(spender, amount);
    require(success, "Approval failed");
}

// ✅ BETTER: Use SafeERC20
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";

contract MyContract {
    using SafeERC20 for IERC20;
    
    function approveToken(address spender, uint256 amount) external {
        token.safeApprove(spender, amount);
    }
}
""",
        references=[
            "https://docs.openzeppelin.com/contracts/4.x/api/token/erc20#SafeERC20",
        ],
        risk_context="Can lead to silent failures in critical operations.",
    ),
    
    "timestamp": RemediationPattern(
        detector_id="timestamp",
        title="Dangerous Block Timestamp Usage",
        summary="Avoid using block.timestamp for critical logic or randomness",
        explanation="""
block.timestamp can be slightly manipulated by miners (within ~15 seconds).
Don't use it for randomness or time-critical financial logic.
""",
        fix_snippet="""
// ❌ VULNERABLE: Using timestamp for randomness
function getWinner() external view returns (uint256) {
    return uint256(keccak256(abi.encodePacked(block.timestamp))) % 100;
}

// ❌ RISKY: Using timestamp for tight deadline
function bid() external payable {
    require(block.timestamp < auctionEnd, "Auction ended");  // ~15 sec manipulation window
}

// ✅ ACCEPTABLE: Coarse time checks (minutes/hours granularity)
function claim() external {
    require(block.timestamp >= vestingStart + 30 days, "Vesting period not ended");
}

// ✅ FOR RANDOMNESS: Use Chainlink VRF
// See: https://docs.chain.link/vrf
""",
        references=[
            "https://swcregistry.io/docs/SWC-116",
            "https://consensys.github.io/smart-contract-best-practices/development-recommendations/solidity-specific/timestamp-dependence/",
            "https://docs.chain.link/vrf",
        ],
        risk_context="Miners can manipulate timestamp by ~15 seconds.",
    ),
    
    "divide-before-multiply": RemediationPattern(
        detector_id="divide-before-multiply",
        title="Divide Before Multiply",
        summary="Perform multiplication before division to preserve precision",
        explanation="""
Solidity performs integer division, which truncates. Dividing before multiplying
loses precision. Always multiply first, then divide.
""",
        fix_snippet="""
// ❌ VULNERABLE: Precision loss
function calculateFee(uint256 amount, uint256 feePercent) external pure returns (uint256) {
    return amount / 100 * feePercent;  // Loses precision!
    // Example: 199 / 100 * 3 = 1 * 3 = 3 (should be ~5.97)
}

// ✅ FIXED: Multiply before divide
function calculateFee(uint256 amount, uint256 feePercent) external pure returns (uint256) {
    return amount * feePercent / 100;
    // Example: 199 * 3 / 100 = 597 / 100 = 5 (closer to correct)
}

// ✅ BETTER: Use basis points for more precision
uint256 constant BASIS_POINTS = 10000;  // 100% = 10000 BP

function calculateFee(uint256 amount, uint256 feeBasisPoints) external pure returns (uint256) {
    return amount * feeBasisPoints / BASIS_POINTS;
}
""",
        references=[
            "https://consensys.github.io/smart-contract-best-practices/development-recommendations/solidity-specific/integer-division/",
        ],
        risk_context="Can lead to financial losses through rounding errors.",
    ),
    
    "shadowing-local": RemediationPattern(
        detector_id="shadowing-local",
        title="Local Variable Shadowing",
        summary="Rename local variables to avoid shadowing state variables",
        explanation="""
When a local variable has the same name as a state variable, the local
variable "shadows" the state variable. This can cause subtle bugs.
""",
        fix_snippet="""
// ❌ VULNERABLE: Local shadows state
contract Token {
    uint256 public totalSupply;
    
    function mint(uint256 totalSupply) external {  // Shadows state!
        // Uses parameter, not state variable
    }
}

// ✅ FIXED: Use different names
contract Token {
    uint256 public totalSupply;
    
    function mint(uint256 amount) external {
        totalSupply += amount;  // Clear which variable is used
    }
}

// ✅ CONVENTION: Prefix parameters with underscore
function setOwner(address _owner) external {
    owner = _owner;
}
""",
        references=[
            "https://swcregistry.io/docs/SWC-119",
        ],
        risk_context="Can cause logic bugs from accessing wrong variable.",
    ),
    
    "calls-loop": RemediationPattern(
        detector_id="calls-loop",
        title="External Calls in Loop",
        summary="Use pull-over-push pattern for payments in loops",
        explanation="""
External calls in loops can fail for various reasons (out of gas, recipient
reverts). If one fails, the entire transaction reverts. Use the withdrawal
pattern instead.
""",
        fix_snippet="""
// ❌ VULNERABLE: External calls in loop
function distributeRewards(address[] calldata recipients) external {
    for (uint i = 0; i < recipients.length; i++) {
        payable(recipients[i]).transfer(reward);  // One failure blocks all!
    }
}

// ✅ FIXED: Pull pattern - let users withdraw
mapping(address => uint256) public pendingWithdrawals;

function recordRewards(address[] calldata recipients, uint256 reward) external onlyOwner {
    for (uint i = 0; i < recipients.length; i++) {
        pendingWithdrawals[recipients[i]] += reward;  // Just update state
    }
}

function withdraw() external {
    uint256 amount = pendingWithdrawals[msg.sender];
    require(amount > 0, "Nothing to withdraw");
    pendingWithdrawals[msg.sender] = 0;
    (bool success, ) = msg.sender.call{value: amount}("");
    require(success, "Transfer failed");
}
""",
        references=[
            "https://consensys.github.io/smart-contract-best-practices/development-recommendations/general/external-calls/#favor-pull-over-push-for-external-calls",
            "https://swcregistry.io/docs/SWC-113",
        ],
        risk_context="Can permanently block operations if any recipient fails.",
    ),
}


# =============================================================================
# MYTHRIL SWC-ID PATTERNS
# Based on Smart Contract Weakness Classification
# =============================================================================

MYTHRIL_PATTERNS: Dict[str, RemediationPattern] = {
    "110": RemediationPattern(
        detector_id="SWC-110",
        title="Exception State (Assert Violation)",
        summary="Use require() for input validation, assert() only for invariants",
        explanation="""
Assert failures indicate an invariant violation - something that should NEVER
happen. If you're using assert() to validate user input, use require() instead.
Assert consumes all remaining gas, while require refunds unused gas.
""",
        fix_snippet="""
// ❌ INCORRECT: Using assert for input validation
function withdraw(uint256 amount) external {
    assert(amount <= balances[msg.sender]);  // Wastes gas on failure!
}

// ✅ CORRECT: Use require for input validation
function withdraw(uint256 amount) external {
    require(amount <= balances[msg.sender], "Insufficient balance");
}

// ✅ CORRECT: Use assert for invariants
function transfer(address to, uint256 amount) external {
    require(balances[msg.sender] >= amount, "Insufficient balance");
    
    uint256 totalBefore = balances[msg.sender] + balances[to];
    balances[msg.sender] -= amount;
    balances[to] += amount;
    
    assert(balances[msg.sender] + balances[to] == totalBefore);  // Invariant check
}
""",
        references=[
            "https://swcregistry.io/docs/SWC-110",
            "https://docs.soliditylang.org/en/latest/control-structures.html#panic-via-assert-and-error-via-require",
        ],
        risk_context="Wastes gas and indicates possible logic errors.",
    ),
    
    "101": RemediationPattern(
        detector_id="SWC-101",
        title="Integer Overflow/Underflow",
        summary="Use Solidity 0.8+ or SafeMath for arithmetic operations",
        explanation="""
Integer overflow/underflow occurs when arithmetic operations exceed the
variable's bounds. Solidity 0.8+ has built-in overflow checks that revert
on overflow. For older versions, use SafeMath.
""",
        fix_snippet="""
// Solidity < 0.8: Use SafeMath
import "@openzeppelin/contracts/utils/math/SafeMath.sol";

contract Token {
    using SafeMath for uint256;
    
    function transfer(uint256 amount) external {
        balances[msg.sender] = balances[msg.sender].sub(amount);  // Safe subtraction
        balances[to] = balances[to].add(amount);  // Safe addition
    }
}

// Solidity >= 0.8: Built-in checks (default)
contract Token {
    function transfer(address to, uint256 amount) external {
        balances[msg.sender] -= amount;  // Reverts on underflow
        balances[to] += amount;  // Reverts on overflow
    }
}

// If you need unchecked math (gas optimization), be careful:
function incrementCounter() external {
    unchecked {
        counter++;  // Won't revert on overflow - use only when safe!
    }
}
""",
        references=[
            "https://swcregistry.io/docs/SWC-101",
            "https://docs.soliditylang.org/en/latest/control-structures.html#checked-or-unchecked-arithmetic",
        ],
        risk_context="Can lead to incorrect calculations and fund theft.",
    ),
    
    "107": RemediationPattern(
        detector_id="SWC-107",
        title="Reentrancy",
        summary="Use Checks-Effects-Interactions pattern and/or ReentrancyGuard",
        explanation="""
Reentrancy allows an attacker to recursively call back into your contract
before the first execution completes. Always update state before making
external calls, and consider using a reentrancy guard.
""",
        fix_snippet="""
// ✅ Use OpenZeppelin ReentrancyGuard
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

contract Vault is ReentrancyGuard {
    mapping(address => uint256) public balances;
    
    function withdraw() external nonReentrant {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "No balance");
        
        balances[msg.sender] = 0;  // Update state BEFORE external call
        
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");
    }
}
""",
        references=[
            "https://swcregistry.io/docs/SWC-107",
            "https://docs.openzeppelin.com/contracts/4.x/api/security#ReentrancyGuard",
        ],
        risk_context="Can drain all funds from a contract.",
    ),
    
    "104": RemediationPattern(
        detector_id="SWC-104",
        title="Unchecked Call Return Value",
        summary="Always check the return value of low-level calls",
        explanation="""
Low-level calls (call, delegatecall, send) return a boolean. If you don't
check it, failed calls continue silently.
""",
        fix_snippet="""
// ❌ VULNERABLE
function sendEther(address to) external {
    to.call{value: 1 ether}("");  // Might fail silently
}

// ✅ FIXED
function sendEther(address to) external {
    (bool success, ) = to.call{value: 1 ether}("");
    require(success, "Transfer failed");
}
""",
        references=[
            "https://swcregistry.io/docs/SWC-104",
        ],
        risk_context="Can lead to silent failures and lost funds.",
    ),
    
    "105": RemediationPattern(
        detector_id="SWC-105",
        title="Unprotected Ether Withdrawal",
        summary="Add access control to functions that withdraw ETH",
        explanation="""
Functions that send ETH to arbitrary addresses without proper access control
can be exploited to drain contract funds.
""",
        fix_snippet="""
// ❌ VULNERABLE
function withdraw() external {
    msg.sender.transfer(address(this).balance);
}

// ✅ FIXED: Add access control
function withdraw() external onlyOwner {
    (bool success, ) = owner.call{value: address(this).balance}("");
    require(success, "Withdrawal failed");
}
""",
        references=[
            "https://swcregistry.io/docs/SWC-105",
        ],
        risk_context="Anyone can drain contract funds.",
    ),
    
    "106": RemediationPattern(
        detector_id="SWC-106",
        title="Unprotected Selfdestruct",
        summary="Add strict access control to selfdestruct",
        explanation="""
An unprotected selfdestruct allows anyone to destroy the contract permanently.
""",
        fix_snippet="""
// ❌ VULNERABLE
function destroy() external {
    selfdestruct(payable(msg.sender));
}

// ✅ FIXED: Multi-sig or timelock
function destroy() external onlyOwner {
    require(destructionApproved, "Not approved");
    selfdestruct(payable(owner));
}
""",
        references=[
            "https://swcregistry.io/docs/SWC-106",
        ],
        risk_context="Permanent contract destruction.",
    ),
    
    "112": RemediationPattern(
        detector_id="SWC-112",
        title="Delegatecall to Untrusted Callee",
        summary="Never delegatecall to user-controlled addresses",
        explanation="""
Delegatecall executes external code in your contract's context. If the
target is user-controlled, attackers can take over your contract.
""",
        fix_snippet="""
// ❌ VULNERABLE
function execute(address target) external {
    target.delegatecall(msg.data);
}

// ✅ FIXED: Whitelist implementations
mapping(address => bool) public trustedImplementations;

function execute(address target, bytes calldata data) external {
    require(trustedImplementations[target], "Untrusted");
    (bool success, ) = target.delegatecall(data);
    require(success, "Failed");
}
""",
        references=[
            "https://swcregistry.io/docs/SWC-112",
        ],
        risk_context="Complete contract takeover possible.",
    ),
    
    "113": RemediationPattern(
        detector_id="SWC-113",
        title="Denial of Service with Failed Call",
        summary="Use pull-over-push pattern for payments",
        explanation="""
If your contract relies on successful external calls to function, a failing
recipient can permanently block operations.
""",
        fix_snippet="""
// ❌ VULNERABLE: Push pattern
function payAll() external {
    for (uint i = 0; i < recipients.length; i++) {
        payable(recipients[i]).transfer(amounts[i]);  // One failure blocks all
    }
}

// ✅ FIXED: Pull pattern
mapping(address => uint256) public pendingWithdrawals;

function withdraw() external {
    uint256 amount = pendingWithdrawals[msg.sender];
    pendingWithdrawals[msg.sender] = 0;
    (bool success, ) = msg.sender.call{value: amount}("");
    require(success, "Failed");
}
""",
        references=[
            "https://swcregistry.io/docs/SWC-113",
        ],
        risk_context="Can permanently freeze contract operations.",
    ),
    
    "115": RemediationPattern(
        detector_id="SWC-115",
        title="Authorization through tx.origin",
        summary="Use msg.sender instead of tx.origin",
        explanation="""
tx.origin can be exploited through phishing attacks. Use msg.sender for
authentication.
""",
        fix_snippet="""
// ❌ VULNERABLE
require(tx.origin == owner);

// ✅ FIXED
require(msg.sender == owner);
""",
        references=[
            "https://swcregistry.io/docs/SWC-115",
        ],
        risk_context="Enables phishing attacks.",
    ),
    
    "116": RemediationPattern(
        detector_id="SWC-116",
        title="Block Values as Source of Randomness",
        summary="Use Chainlink VRF for randomness, not block values",
        explanation="""
Block values (timestamp, blockhash) can be manipulated by miners. Don't use
them for randomness in high-value scenarios.
""",
        fix_snippet="""
// ❌ VULNERABLE
uint256 random = uint256(blockhash(block.number - 1));

// ✅ FIXED: Use Chainlink VRF
// See: https://docs.chain.link/vrf
""",
        references=[
            "https://swcregistry.io/docs/SWC-116",
            "https://docs.chain.link/vrf",
        ],
        risk_context="Miners can predict/manipulate results.",
    ),
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_pattern_for_detector(detector_id: str) -> Optional[RemediationPattern]:
    """
    Get the remediation pattern for a Slither detector ID.
    
    Args:
        detector_id: The Slither detector ID (e.g., "reentrancy-eth")
        
    Returns:
        RemediationPattern if found, None otherwise
    """
    return SLITHER_PATTERNS.get(detector_id.lower())


def get_pattern_for_swc(swc_id: str) -> Optional[RemediationPattern]:
    """
    Get the remediation pattern for a Mythril SWC ID.
    
    Args:
        swc_id: The SWC ID (e.g., "110" or "SWC-110")
        
    Returns:
        RemediationPattern if found, None otherwise
    """
    # Normalize SWC ID (remove "SWC-" prefix if present)
    normalized = swc_id.replace("SWC-", "").strip()
    return MYTHRIL_PATTERNS.get(normalized)


def get_all_supported_detectors() -> Dict[str, list]:
    """
    Get a list of all supported detector IDs.
    
    Returns:
        Dictionary with 'slither' and 'mythril' keys containing detector ID lists
    """
    return {
        "slither": list(SLITHER_PATTERNS.keys()),
        "mythril": list(MYTHRIL_PATTERNS.keys()),
    }
