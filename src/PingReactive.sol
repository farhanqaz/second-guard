// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {AbstractReactive} from "reactive-lib-omni/base/AbstractReactive.sol";
import {IReactive} from "reactive-lib-omni/interfaces/IReactive.sol";
import {ISystemContract} from "reactive-lib-omni/interfaces/ISystemContract.sol";

/// @title PingReactive
/// @notice Reactive contract on Lasna that subscribes to Ping on Base Sepolia and requests a callback
///         back to the sink, carrying the ping timestamp and block so the loop can be measured.
/// @dev Built against reactive-lib-omni. The legacy reactive-lib does not match Omni: its SYSTEM address,
///      vm detection and Callback event path all differ, and the deprecated Callback event is rejected by
///      the relay with "invalid payload format".
contract PingReactive is AbstractReactive {
    uint256 public immutable originChainId;
    uint256 public immutable destinationChainId;
    address public immutable deployer;

    address public sink;
    uint256 public handled;
    uint64 public gasLimit = 400_000;

    constructor(uint256 originChainId_, uint256 destinationChainId_, address originContract_, uint256 topic0_) payable {
        originChainId = originChainId_;
        destinationChainId = destinationChainId_;
        deployer = msg.sender;
        SYSTEM.subscribe(originChainId_, originContract_, topic0_, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE);
    }

    /// @notice Set once after the sink exists: the sink needs this address, so the dependency is circular.
    function setSink(address sink_) external {
        require(msg.sender == deployer, "deployer only");
        sink = sink_;
    }

    function payload(uint256 nonce, uint256 pingTimestamp, uint256 pingBlock) public pure returns (bytes memory) {
        return
            abi.encodeWithSignature(
                "pong(address,uint256,uint256,uint256)", address(0), nonce, pingTimestamp, pingBlock
            );
    }

    function react(LogRecord calldata log_) external onlySystem {
        uint256 nonce = log_.topic2;
        (uint256 pingTimestamp, uint256 pingBlock) = abi.decode(log_.data, (uint256, uint256));
        handled += 1;
        if (sink == address(0)) return;
        SYSTEM.requestCallbackV_1_0(
            ISystemContract.CallbackConfiguration_V_1_0({
                chainId: destinationChainId,
                recipient: sink,
                gasLimit: gasLimit,
                payload: payload(nonce, pingTimestamp, pingBlock)
            })
        );
    }
}
