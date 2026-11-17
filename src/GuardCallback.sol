// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {AbstractCallback} from "reactive-lib-omni/base/AbstractCallback.sol";
import {IPayable} from "reactive-lib-omni/interfaces/IPayable.sol";
import {MiniPool} from "./MiniPool.sol";

/// @title GuardCallback
/// @notice Receives the guard's pause instruction on a destination chain and stops the venue.
/// @dev Deployed after the reactive contract (the network injects that address into the payload), then
///      registered on it with setCallbacks().
contract GuardCallback is AbstractCallback {
    MiniPool public immutable pool;

    event GuardTripped(
        address indexed reactive,
        uint256 priceA,
        uint256 priceB,
        uint256 divergenceBps,
        uint256 sourceBlock,
        uint256 arrivedAt
    );

    constructor(IPayable callbackProxy_, address callbackSender_, MiniPool pool_)
        payable
        AbstractCallback(callbackProxy_, callbackSender_)
    {
        pool = pool_;
    }

    function pauseFromGuard(
        address reactive_,
        uint256 priceA,
        uint256 priceB,
        uint256 divergenceBps,
        uint256 sourceBlock
    ) external onlyServiceProvider onlyCallbackSender(reactive_) {
        pool.pause("cross-venue divergence");
        emit GuardTripped(reactive_, priceA, priceB, divergenceBps, sourceBlock, block.timestamp);
    }
}
