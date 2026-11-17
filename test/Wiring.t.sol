// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {Test} from "forge-std/Test.sol";
import {DivergenceGuard} from "../src/DivergenceGuard.sol";
import {ISystemContract} from "reactive-lib-omni/interfaces/ISystemContract.sol";
import {IReactive} from "reactive-lib-omni/interfaces/IReactive.sol";

/// @notice Stand-in for the Reactive system contract, etched at 0x8888... so the guard's callback requests
///         can be inspected without a live network.
contract MockSystem {
    struct Req {
        uint256 chainId;
        address recipient;
        uint64 gasLimit;
        bytes payload;
    }

    Req[] public requests;
    uint256 public subscriptions;

    function subscribe(uint256, address, uint256, uint256, uint256, uint256) external {
        subscriptions += 1;
    }

    function unsubscribe(uint256, address, uint256, uint256, uint256, uint256) external {}

    function requestCallback(ISystemContract.CallbackVersion, bytes memory) external {}

    function requestCallbackV_1_0(ISystemContract.CallbackConfiguration_V_1_0 memory config) external {
        requests.push(Req(config.chainId, config.recipient, config.gasLimit, config.payload));
    }

    function debt(address) external pure returns (uint256) {
        return 0;
    }

    function count() external view returns (uint256) {
        return requests.length;
    }

    receive() external payable {}
}

contract WiringTest is Test {
    DivergenceGuard guard;
    MockSystem system;

    address payable constant SYSTEM = payable(0x8888888888888888888888888888888888888888);
    uint256 constant TOPIC = 0x9d769942b8f5a8c9cae56e1d9b2c9798fcb63e0dd0e5fac263bb31b2d7cb5eac;

    function setUp() public {
        system = new MockSystem();
        vm.etch(SYSTEM, address(system).code);
        vm.deal(SYSTEM, 1 ether);

        uint256[] memory ids = new uint256[](2);
        ids[0] = 84532;
        ids[1] = 1301;
        address[] memory pools = new address[](2);
        pools[0] = address(0xA11CE);
        pools[1] = address(0xB0B);

        guard = new DivergenceGuard(ids, pools, TOPIC, 500, 300, 60);
        guard.setCallbacks(address(0xCA11), address(0xCA12));
    }

    function testSubscribesToBothVenues() public view {
        assertEq(MockSystem(SYSTEM).subscriptions(), 2);
    }

    function testRequestsTwoPauseCallbacks() public {
        _push(84532, 1e18);
        _push(1301, 1.2e18);

        MockSystem sys = MockSystem(SYSTEM);
        assertEq(sys.count(), 2, "one pause request per venue");

        (uint256 chainA, address recipA, uint64 gasA, bytes memory payloadA) = sys.requests(0);
        assertEq(chainA, 84532);
        assertEq(recipA, address(0xCA11));
        assertEq(gasA, 400_000);

        (address placeholder, uint256 pa, uint256 pb, uint256 bps, uint256 srcBlock) =
            abi.decode(_strip(payloadA), (address, uint256, uint256, uint256, uint256));
        assertEq(placeholder, address(0), "first slot must be free for the injected sender");
        assertEq(pa, 1e18);
        assertEq(pb, 1.2e18);
        assertEq(bps, 1818);
        assertEq(srcBlock, 1);

        (uint256 chainB, address recipB,,) = sys.requests(1);
        assertEq(chainB, 1301);
        assertEq(recipB, address(0xCA12));
    }

    function testNoRequestWhenUnderThreshold() public {
        _push(84532, 1e18);
        _push(1301, 1.03e18);
        assertEq(MockSystem(SYSTEM).count(), 0);
    }

    function _push(uint256 chainId, uint256 price) internal {
        vm.prank(SYSTEM);
        guard.react(
            IReactive.LogRecord({
                chainId: chainId,
                contractAddress: address(0),
                topic0: TOPIC,
                topic1: 0,
                topic2: 0,
                topic3: 0,
                data: abi.encode(price),
                blockNumber: 1,
                opCode: 3,
                blockHash: 0,
                txHash: 0,
                logIndex: 0
            })
        );
    }

    function _strip(bytes memory data) internal pure returns (bytes memory out) {
        out = new bytes(data.length - 4);
        for (uint256 i = 0; i < out.length; i++) {
            out[i] = data[i + 4];
        }
    }
}
