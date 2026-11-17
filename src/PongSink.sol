// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {AbstractCallback} from "reactive-lib-omni/base/AbstractCallback.sol";
import {IPayable} from "reactive-lib-omni/interfaces/IPayable.sol";

/// @title PongSink
/// @notice Destination contract on Base Sepolia. Records when the callback actually landed, plus the
///         address the network injected into the first payload slot.
contract PongSink is AbstractCallback {
    event Pong(
        uint256 indexed nonce,
        uint256 pingTimestamp,
        uint256 pingBlock,
        uint256 arrivedTimestamp,
        uint256 arrivedBlock,
        address reactive
    );

    constructor(IPayable callbackProxy_, address callbackSender_)
        payable
        AbstractCallback(callbackProxy_, callbackSender_)
    {}

    function pong(address reactive_, uint256 nonce, uint256 pingTimestamp, uint256 pingBlock)
        external
        onlyServiceProvider
        onlyCallbackSender(reactive_)
    {
        emit Pong(nonce, pingTimestamp, pingBlock, block.timestamp, block.number, reactive_);
    }
}
