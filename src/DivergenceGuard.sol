// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {AbstractReactive} from "reactive-lib-omni/base/AbstractReactive.sol";
import {IReactive} from "reactive-lib-omni/interfaces/IReactive.sol";
import {ISystemContract} from "reactive-lib-omni/interfaces/ISystemContract.sol";

/// @title DivergenceGuard
/// @notice Cross-venue price guard on Reactive Lasna. It subscribes to Swap events on the same pair in two
///         different chains, keeps the latest price per chain in its own RVM state, and when the two venues
///         diverge past a threshold it asks both chains to pause their venue in one shot.
/// @dev This is the part a same-chain watchdog cannot do: the divergence only exists across two chains, and
///      the rule needs both feeds inside one deterministic execution.
contract DivergenceGuard is AbstractReactive {
    struct Venue {
        uint256 chainId;
        address pool;
        address callback;
    }

    Venue[] public venues;

    mapping(uint256 => uint256) public price; // chainId => price, 1e18
    mapping(uint256 => uint256) public updatedAt; // chainId => lasna timestamp of the last update

    uint256 public thresholdBps;
    uint256 public maxStaleness;
    uint256 public cooldown;
    uint256 public lastTriggerAt;
    uint256 public triggers;
    bool public armed = true;

    address public immutable deployer;
    uint64 public gasLimit = 400_000;

    event Divergence(uint256 indexed chainA, uint256 priceA, uint256 chainB, uint256 priceB, uint256 bps);
    event Tripped(uint256 bps, uint256 chainA, uint256 priceA, uint256 chainB, uint256 priceB, uint256 at);
    event PriceUpdated(uint256 indexed chainId, uint256 price, uint256 at);

    constructor(
        uint256[] memory chainIds_,
        address[] memory pools_,
        uint256 topic0_,
        uint256 thresholdBps_,
        uint256 maxStaleness_,
        uint256 cooldown_
    ) payable {
        require(chainIds_.length == 2 && pools_.length == 2, "two venues");
        deployer = msg.sender;
        thresholdBps = thresholdBps_;
        maxStaleness = maxStaleness_;
        cooldown = cooldown_;

        bool onChain = address(SYSTEM).code.length > 0;
        for (uint256 i = 0; i < 2; i++) {
            venues.push(Venue({chainId: chainIds_[i], pool: pools_[i], callback: address(0)}));
            if (onChain) {
                SYSTEM.subscribe(chainIds_[i], pools_[i], topic0_, REACTIVE_IGNORE, REACTIVE_IGNORE, REACTIVE_IGNORE);
            }
        }
    }

    // ------------------------------------------------------------------ admin

    modifier onlyDeployer() {
        require(msg.sender == deployer, "deployer only");
        _;
    }

    function setCallbacks(address callbackA, address callbackB) external onlyDeployer {
        venues[0].callback = callbackA;
        venues[1].callback = callbackB;
    }

    function setThreshold(uint256 bps) external onlyDeployer {
        thresholdBps = bps;
    }

    function setArmed(bool armed_) external onlyDeployer {
        armed = armed_;
    }

    function venueCount() external view returns (uint256) {
        return venues.length;
    }

    function venueAt(uint256 i) external view returns (Venue memory) {
        return venues[i];
    }

    // ------------------------------------------------------------- the rule

    /// @notice Pure divergence calculation in basis points of the midpoint.
    function divergenceBps(uint256 priceA, uint256 priceB) public pure returns (uint256) {
        if (priceA == 0 || priceB == 0) return 0;
        uint256 diff = priceA > priceB ? priceA - priceB : priceB - priceA;
        uint256 mid = (priceA + priceB) / 2;
        if (mid == 0) return 0;
        return (diff * 10_000) / mid;
    }

    function react(LogRecord calldata log_) external onlySystem {
        uint256 chainId = log_.chainId;
        // MiniPool.Swap data layout: amountIn, amountOut, priceAInB, reserveA, reserveB
        uint256 newPrice;
        if (log_.data.length >= 160) {
            (,, newPrice,,) = abi.decode(log_.data, (uint256, uint256, uint256, uint256, uint256));
        } else {
            newPrice = abi.decode(log_.data, (uint256));
        }
        if (newPrice == 0) return;

        price[chainId] = newPrice;
        updatedAt[chainId] = block.timestamp;
        emit PriceUpdated(chainId, newPrice, block.timestamp);

        if (!armed || venues.length != 2) return;

        uint256 a = venues[0].chainId;
        uint256 b = venues[1].chainId;
        uint256 pa = price[a];
        uint256 pb = price[b];
        if (pa == 0 || pb == 0) return;
        // both feeds must be fresh, otherwise the comparison is against a dead venue
        if (block.timestamp > updatedAt[a] + maxStaleness || block.timestamp > updatedAt[b] + maxStaleness) return;

        uint256 bps = divergenceBps(pa, pb);
        emit Divergence(a, pa, b, pb, bps);
        if (bps <= thresholdBps) return;
        if (lastTriggerAt != 0 && block.timestamp < lastTriggerAt + cooldown) return;

        lastTriggerAt = block.timestamp;
        triggers += 1;
        emit Tripped(bps, a, pa, b, pb, block.timestamp);

        _requestPause(0, pa, pb, bps, log_.blockNumber);
        _requestPause(1, pa, pb, bps, log_.blockNumber);
    }

    function _requestPause(uint256 index, uint256 pa, uint256 pb, uint256 bps, uint256 sourceBlock) internal {
        Venue memory v = venues[index];
        if (v.callback == address(0)) return;
        bytes memory payload = abi.encodeWithSignature(
            "pauseFromGuard(address,uint256,uint256,uint256,uint256)", address(0), pa, pb, bps, sourceBlock
        );
        if (address(SYSTEM).code.length == 0) return; // local test VM has no system contract
        SYSTEM.requestCallbackV_1_0(
            ISystemContract.CallbackConfiguration_V_1_0({
                chainId: v.chainId, recipient: v.callback, gasLimit: gasLimit, payload: payload
            })
        );
    }
}
