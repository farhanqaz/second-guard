// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {AbstractCallback} from "reactive-lib/abstract-base/AbstractCallback.sol";

/// @notice Destination contract on Base Sepolia. Records when the callback actually landed.
contract PongSink is AbstractCallback {
    event Pong(
        uint256 indexed nonce,
        uint256 pingTimestamp,
        uint256 pingBlock,
        uint256 arrivedTimestamp,
        uint256 arrivedBlock
    );

    constructor(address callbackSender) AbstractCallback(callbackSender) {}

    function pong(address rvmId, uint256 nonce, uint256 pingTimestamp, uint256 pingBlock)
        external
        authorizedSenderOnly
        rvmIdOnly(rvmId)
    {
        emit Pong(nonce, pingTimestamp, pingBlock, block.timestamp, block.number);
    }
}
