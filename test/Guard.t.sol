// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {Test} from "forge-std/Test.sol";
import {MiniERC20} from "../src/MiniERC20.sol";
import {MiniPool} from "../src/MiniPool.sol";
import {DivergenceGuard} from "../src/DivergenceGuard.sol";
import {IReactive} from "reactive-lib-omni/interfaces/IReactive.sol";

contract PoolTest is Test {
    MiniERC20 a;
    MiniERC20 b;
    MiniPool pool;

    address constant GUARD = address(0x600D);

    function setUp() public {
        a = new MiniERC20("Alpha", "A");
        b = new MiniERC20("Beta", "B");
        pool = new MiniPool(a, b);
        a.mint(address(this), 1_000_000e18);
        b.mint(address(this), 1_000_000e18);
        a.approve(address(pool), type(uint256).max);
        b.approve(address(pool), type(uint256).max);
        pool.seed(1_000e18, 1_000e18);
        pool.setGuard(GUARD);
    }

    function testSeedPriceIsOne() public view {
        assertEq(pool.price(), 1e18);
    }

    function testSwapMovesPrice() public {
        uint256 out = pool.swap(true, 10e18);
        assertGt(out, 0);
        assertGt(pool.price(), 1e18, "A in makes A relatively more expensive");
        assertEq(pool.swaps(), 1);
    }

    function testSwapRevertsWhenPaused() public {
        vm.prank(GUARD);
        pool.pause("test");
        assertTrue(pool.paused());
        vm.expectRevert("pool paused");
        pool.swap(true, 1e18);
    }

    function testOnlyGuardCanPause() public {
        vm.expectRevert("guard only");
        pool.pause("nope");
    }

    function testGuardCannotBeReset() public {
        vm.expectRevert("guard set");
        pool.setGuard(address(0xBEEF));
    }
}

contract DivergenceTest is Test {
    DivergenceGuard guard;
    address constant SYSTEM = 0x8888888888888888888888888888888888888888;
    uint256 constant TOPIC = 0x9d769942b8f5a8c9cae56e1d9b2c9798fcb63e0dd0e5fac263bb31b2d7cb5eac;
    uint256 constant BASE = 84532;
    uint256 constant UNI = 1301;

    function setUp() public {
        uint256[] memory ids = new uint256[](2);
        ids[0] = BASE;
        ids[1] = UNI;
        address[] memory pools = new address[](2);
        pools[0] = address(0xA11CE);
        pools[1] = address(0xB0B);
        guard = new DivergenceGuard(ids, pools, TOPIC, 500, 300, 60);
        guard.setCallbacks(address(0xCA11), address(0xCA12));
    }

    function _record(uint256 chainId, uint256 newPrice) internal pure returns (IReactive.LogRecord memory) {
        return IReactive.LogRecord({
            chainId: chainId,
            contractAddress: address(0),
            topic0: TOPIC,
            topic1: 0,
            topic2: 0,
            topic3: 0,
            data: abi.encode(newPrice),
            blockNumber: 1,
            opCode: 3,
            blockHash: 0,
            txHash: 0,
            logIndex: 0
        });
    }

    function testDivergenceMath() public view {
        assertEq(guard.divergenceBps(1e18, 1e18), 0);
        assertEq(guard.divergenceBps(1e18, 1.02e18), 198); // 0.02 / 1.01
        assertEq(guard.divergenceBps(1e18, 1e18 * 2), 6666); // 1 / 1.5
    }

    function testNoTripBelowThreshold() public {
        vm.startPrank(SYSTEM);
        guard.react(_record(BASE, 1e18));
        guard.react(_record(UNI, 1.02e18));
        vm.stopPrank();
        assertEq(guard.triggers(), 0);
    }

    function testTripsAboveThreshold() public {
        vm.startPrank(SYSTEM);
        guard.react(_record(BASE, 1e18));
        guard.react(_record(UNI, 1.2e18));
        vm.stopPrank();
        assertEq(guard.triggers(), 1);
        assertEq(guard.divergenceBps(1e18, 1.2e18), 1818);
    }

    function testNoTripOnStaleFeed() public {
        vm.prank(SYSTEM);
        guard.react(_record(BASE, 1e18));
        vm.warp(block.timestamp + 301); // beyond maxStaleness
        vm.prank(SYSTEM);
        guard.react(_record(UNI, 1.3e18));
        assertEq(guard.triggers(), 0);
    }

    function testCooldownBlocksSecondTrip() public {
        vm.startPrank(SYSTEM);
        guard.react(_record(BASE, 1e18));
        guard.react(_record(UNI, 2e18));
        guard.react(_record(BASE, 1.1e18));
        vm.stopPrank();
        assertEq(guard.triggers(), 1);
    }

    function testReactRejectsStranger() public {
        vm.expectRevert();
        guard.react(_record(BASE, 1e18));
    }
}
