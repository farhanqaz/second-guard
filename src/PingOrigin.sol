// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @notice Origin contract on Base Sepolia. Emits the event the reactive contract watches.
contract PingOrigin {
    event Ping(address indexed sender, uint256 indexed nonce, uint256 sentAt, uint256 pingBlock);

    function ping(uint256 nonce) external {
        emit Ping(msg.sender, nonce, block.timestamp, block.number);
    }
}
