// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IReactive} from "reactive-lib/interfaces/IReactive.sol";
import {ISystemContract} from "reactive-lib/interfaces/ISystemContract.sol";
import {AbstractReactive} from "reactive-lib/abstract-base/AbstractReactive.sol";

/// @notice Reactive contract on Lasna. Subscribes to Ping on the origin chain and fires a callback
///         back to the destination chain, carrying the ping's timestamp and block so the loop can be measured.
contract PingReactive is IReactive, AbstractReactive {
    uint256 public originChainId;
    uint256 public destinationChainId;
    address public sink;
    uint256 public handled;

    uint64 private constant GAS_LIMIT = 400_000;

    constructor(
        uint256 _originChainId,
        uint256 _destinationChainId,
        address _originContract,
        uint256 _pingTopic,
        address _sink
    ) {
        originChainId = _originChainId;
        destinationChainId = _destinationChainId;
        sink = _sink;

        if (!vm) {
            service.subscribe(
                _originChainId, _originContract, _pingTopic, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE
            );
        }
    }

    /// @notice Builds the callback payload. First slot stays address(0): the RVM ID is injected there.
    function payload(uint256 nonce, uint256 pingTimestamp, uint256 pingBlock) public pure returns (bytes memory) {
        return abi.encodeWithSignature("pong(address,uint256,uint256,uint256)", address(0), nonce, pingTimestamp, pingBlock);
    }

    function react(LogRecord calldata log) external vmOnly {
        uint256 nonce = log.topic_2;
        (uint256 pingTimestamp, uint256 pingBlock) = abi.decode(log.data, (uint256, uint256));
        handled += 1;
        emit Callback(destinationChainId, sink, GAS_LIMIT, payload(nonce, pingTimestamp, pingBlock));
    }
}
