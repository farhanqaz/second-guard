// SPDX-License-Identifier: MIT
pragma solidity ^0.8.29;

import {Test} from "forge-std/Test.sol";
import {PingOrigin} from "../src/PingOrigin.sol";
import {PongSink} from "../src/PongSink.sol";
import {IPayable} from "reactive-lib-omni/interfaces/IPayable.sol";
import {AbstractPayer} from "reactive-lib-omni/base/AbstractPayer.sol";

contract LoopTest is Test {
    PingOrigin origin;
    PongSink sink;

    address payable constant PROXY = payable(address(0xBEEF));
    address constant REACTIVE = address(0xCAFE);

    function setUp() public {
        origin = new PingOrigin();
        sink = new PongSink(IPayable(PROXY), REACTIVE);
    }

    function testOriginEmitsPing() public {
        vm.expectEmit(true, true, true, true, address(origin));
        emit PingOrigin.Ping(address(this), 7, block.timestamp, block.number);
        origin.ping(7);
    }

    function testSinkAcceptsProxyOnly() public {
        vm.expectEmit(true, true, true, true, address(sink));
        emit PongSink.Pong(7, 111, 222, block.timestamp, block.number, REACTIVE);
        vm.prank(PROXY);
        sink.pong(REACTIVE, 7, 111, 222);
    }

    function testSinkRejectsStranger() public {
        vm.prank(address(0x1234));
        vm.expectRevert(abi.encodeWithSelector(AbstractPayer.NotAuthorized.selector, address(0x1234), PROXY));
        sink.pong(REACTIVE, 7, 111, 222);
    }

    function testSinkRejectsWrongReactive() public {
        vm.prank(PROXY);
        vm.expectRevert();
        sink.pong(address(0xDEAD), 7, 111, 222);
    }

    function testPayloadLayout() public {
        PayloadHarness h = new PayloadHarness();
        bytes memory p = h.payload(7, 1_700_000_000, 12_345);
        (address first, uint256 nonce, uint256 ts, uint256 blk) =
            abi.decode(slice4(p), (address, uint256, uint256, uint256));
        assertEq(first, address(0), "first slot must be address(0) for the injected sender");
        assertEq(nonce, 7);
        assertEq(ts, 1_700_000_000);
        assertEq(blk, 12_345);
    }

    /// @dev drops the 4-byte selector so the arguments can be decoded
    function slice4(bytes memory data) internal pure returns (bytes memory out) {
        out = new bytes(data.length - 4);
        for (uint256 i = 0; i < out.length; i++) {
            out[i] = data[i + 4];
        }
    }
}

contract PayloadHarness {
    function payload(uint256 nonce, uint256 pingTimestamp, uint256 pingBlock) public pure returns (bytes memory) {
        return
            abi.encodeWithSignature(
                "pong(address,uint256,uint256,uint256)", address(0), nonce, pingTimestamp, pingBlock
            );
    }
}
